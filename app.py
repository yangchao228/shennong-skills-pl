#!/usr/bin/env python3
"""Skills Manager - Web interface for managing and evolving AI skills"""

from flask import Flask, jsonify, request, send_from_directory, Response, stream_with_context
from flask_cors import CORS
import os, re, json, yaml, shutil, threading, time, queue, hashlib
from pathlib import Path
from datetime import datetime
from typing import Generator
from difflib import SequenceMatcher

app = Flask(__name__, static_folder='static')
CORS(app)

# ── Global notification queue (SSE to browser) ───────────────
_notification_clients: list[queue.Queue] = []
_notification_lock = threading.Lock()

def broadcast_notification(data: dict):
    """Push a notification to all connected browser clients."""
    with _notification_lock:
        dead = []
        for q in _notification_clients:
            try:
                q.put_nowait(data)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _notification_clients.remove(q)

# ── File watcher ─────────────────────────────────────────────
_watcher_started = False

def start_watcher():
    global _watcher_started
    if _watcher_started:
        return

    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers.polling import PollingObserver
    except ImportError:
        print("  watchdog not installed — file watching disabled")
        return

    class SkillFileHandler(FileSystemEventHandler):
        def __init__(self):
            self._debounce: dict[str, float] = {}

        def on_modified(self, event):
            if event.is_directory:
                return
            p = Path(event.src_path)
            if p.name != "SKILL.md":
                return
            # Debounce: ignore repeated events within 2 seconds
            now = time.time()
            key = str(p)
            if now - self._debounce.get(key, 0) < 2.0:
                return
            self._debounce[key] = now

            skill_id = p.parent.name
            threading.Thread(
                target=handle_skill_changed,
                args=(skill_id, p.parent),
                daemon=True
            ).start()

    def handle_skill_changed(skill_id: str, skill_dir: Path):
        """Run after a SKILL.md is modified externally."""
        test_file = get_test_cases_file(skill_dir)
        meta = load_meta(skill_dir)

        broadcast_notification({
            "type": "file_changed",
            "skill_id": skill_id,
            "message": f"检测到 {skill_id}/SKILL.md 已修改",
            "has_tests": has_test_cases(skill_dir),
        })

        if not test_file.exists():
            # No tests → just notify, nothing more to do
            return

        # Run tests and compare to stored baseline
        try:
            cases = json.loads(test_file.read_text())["cases"]
            content = skill_dir / "SKILL.md"
            results = [run_test_case(content.read_text(encoding='utf-8'), tc) for tc in cases]
            new_score = compute_skill_score(results)
        except Exception as e:
            broadcast_notification({
                "type": "test_error",
                "skill_id": skill_id,
                "message": f"{skill_id} 测试运行失败: {e}",
            })
            return

        prev_score = meta.get("last_score")
        # Save new score
        meta["last_score"] = round(new_score, 4)
        meta["last_tested"] = datetime.now().isoformat()
        save_meta(skill_dir, meta)

        if prev_score is None:
            # First time — just record baseline
            broadcast_notification({
                "type": "test_done",
                "skill_id": skill_id,
                "score": new_score,
                "prev_score": None,
                "delta": None,
                "severity": "info",
                "message": f"{skill_id} 首次测试基线 {new_score:.1%}",
            })
            return

        delta = new_score - prev_score
        threshold_auto   = -0.10   # ≥10% drop  → auto-evolve
        threshold_warn   = -0.01   # any drop   → warn

        if delta >= 0:
            broadcast_notification({
                "type": "test_done",
                "skill_id": skill_id,
                "score": new_score,
                "prev_score": prev_score,
                "delta": round(delta, 4),
                "severity": "ok",
                "message": f"{skill_id} 修改后分数持平或提升 {prev_score:.1%} → {new_score:.1%}",
            })
        elif delta >= threshold_auto:
            broadcast_notification({
                "type": "test_done",
                "skill_id": skill_id,
                "score": new_score,
                "prev_score": prev_score,
                "delta": round(delta, 4),
                "severity": "warn",
                "message": f"{skill_id} 小幅下降 {prev_score:.1%} → {new_score:.1%}，建议检查",
            })
        else:
            # Significant drop → auto-start evolution
            broadcast_notification({
                "type": "auto_evolve_start",
                "skill_id": skill_id,
                "score": new_score,
                "prev_score": prev_score,
                "delta": round(delta, 4),
                "message": f"{skill_id} 下降 {delta:.1%}，自动触发进化...",
            })
            # Run evolution in background; stream events via broadcast
            for evo_event_str in evolution_stream(skill_dir, max_rounds=5):
                # evo_event_str is "data: {...}\n\n"
                try:
                    payload = json.loads(evo_event_str[6:].strip())
                    payload["skill_id"] = skill_id
                    payload["source"] = "auto_evolve"
                    broadcast_notification(payload)
                except Exception:
                    pass
            broadcast_notification({
                "type": "auto_evolve_end",
                "skill_id": skill_id,
                "message": f"{skill_id} 自动进化完成",
            })

    skills_path = get_skills_path()
    if not skills_path.exists():
        skills_path.mkdir(parents=True, exist_ok=True)

    try:
        observer = PollingObserver()
        observer.schedule(SkillFileHandler(), str(skills_path), recursive=True)
        observer.daemon = True
        observer.start()
        print(f"  👁  Watching {skills_path} for changes (polling)")
    except Exception as e:
        print(f"  polling watcher failed — file watching disabled: {e}")
        return

    _watcher_started = True

# ── Config ──────────────────────────────────────────────────
def get_skills_path() -> Path:
    env = os.environ.get("SKILLS_PATH")
    if env: return Path(env)
    local = Path(".claude") / "skills"
    if local.exists(): return local
    return Path.home() / ".claude" / "skills"

def get_manager_meta_root() -> Path:
    env = os.environ.get("SKILLS_MANAGER_META_DIR") or ""
    if env:
        return Path(env).expanduser()
    return Path("runtime") / "meta"

def get_write_protected_roots() -> list[Path]:
    raw = os.environ.get("SKILLS_MANAGER_PROTECTED_ROOTS") or ""
    if raw:
        return [Path(p).expanduser().resolve() for p in raw.split(os.pathsep) if p.strip()]
    return [(Path.home() / ".codex" / "skills").resolve()]

def path_is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False

def is_write_protected_skill(skill_dir: Path) -> bool:
    resolved = skill_dir.expanduser().resolve()
    return any(path_is_relative_to(resolved, root) for root in get_write_protected_roots())

def write_protection_status(skill_dir: Path) -> dict:
    protected = is_write_protected_skill(skill_dir)
    return {
        "protected": protected,
        "reason": "external_skill_root" if protected else None,
        "requires_confirm_write": protected,
        "protected_roots": [str(p) for p in get_write_protected_roots()],
    }

def request_confirmed_write() -> bool:
    payload = request.get_json(silent=True) or {}
    query_value = request.args.get("confirm_write", "")
    return bool(payload.get("confirm_write")) or query_value.lower() in {"1", "true", "yes"}

def write_protection_error(skill_dir: Path):
    return jsonify({
        "error": "Write confirmation required",
        "message": "这是外部安装 skill。该操作会覆盖真实 SKILL.md，需要显式 confirm_write=true。",
        "write_protection": write_protection_status(skill_dir),
    }), 409

def get_skill_state_dir(skill_dir: Path) -> Path:
    resolved = str(skill_dir.expanduser().resolve())
    digest = hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:16]
    return get_manager_meta_root() / digest

def ensure_skill_state_dir(skill_dir: Path) -> Path:
    state_dir = get_skill_state_dir(skill_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    pointer = state_dir / "skill-path.json"
    if not pointer.exists():
        pointer.write_text(
            json.dumps({"skill_path": str(skill_dir.expanduser().resolve())}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return state_dir

def get_test_cases_file(skill_dir: Path, for_write: bool = False) -> Path:
    state_file = get_skill_state_dir(skill_dir) / "test-cases.json"
    if for_write:
        return ensure_skill_state_dir(skill_dir) / "test-cases.json"
    legacy_file = skill_dir / "test-cases.json"
    return state_file if state_file.exists() else legacy_file

def has_test_cases(skill_dir: Path) -> bool:
    return (get_skill_state_dir(skill_dir) / "test-cases.json").exists() or (skill_dir / "test-cases.json").exists()

# ── Core helpers ────────────────────────────────────────────
def parse_frontmatter(content: str) -> dict:
    if not content.startswith('---'): return {}
    try:
        end = content.index('---', 3)
        return yaml.safe_load(content[3:end].strip()) or {}
    except Exception:
        result = {}
        for line in content[3:].split('\n'):
            if line.strip() == '---': break
            if ':' in line:
                k, _, v = line.partition(':')
                result[k.strip()] = v.strip()
        return result

GENERATED_REF_PREFIXES = (
    "decoded/",
    "final/",
    "frames/",
    "prompts/",
    "qa/",
    "references/",
    "run/",
)
GENERATED_REF_NAMES = {
    "imagegen-jobs.json",
    "pet_request.json",
    "pet.json",
}

def is_generated_or_placeholder_ref(ref: str) -> bool:
    if any(token in ref for token in ("<", ">", "$", "{", "}")):
        return True
    return ref in GENERATED_REF_NAMES or ref.startswith(GENERATED_REF_PREFIXES)

def referenced_file_exists(skill_dir: Path, ref: str) -> bool:
    path = Path(ref)
    candidates = [skill_dir / path]
    if len(path.parts) == 1 and path.suffix in {".py", ".sh"}:
        candidates.append(skill_dir / "scripts" / path)
    return any(candidate.exists() for candidate in candidates)

def check_health(skill_dir: Path) -> dict:
    def issue(kind: str, severity: str, message: str, dimension: str, impact: str) -> dict:
        return {
            "kind": kind,
            "severity": severity,
            "message": message,
            "dimension": dimension,
            "impact": impact,
        }

    def finalize(issues: list[dict], score: int) -> dict:
        groups = {
            "blocking": [i for i in issues if i["kind"] == "blocking"],
            "risk": [i for i in issues if i["kind"] == "risk"],
            "optimization": [i for i in issues if i["kind"] == "optimization"],
        }
        grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D"
        return {
            "score": score,
            "grade": grade,
            "issues": issues,
            "groups": groups,
            "counts": {k: len(v) for k, v in groups.items()},
            "summary": {
                "has_blocking": bool(groups["blocking"]),
                "has_risk": bool(groups["risk"]),
                "has_optimization": bool(groups["optimization"]),
                "status": "blocking" if groups["blocking"] else "risk" if groups["risk"] else "healthy",
            },
        }

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return finalize([
            issue("blocking", "error", "SKILL.md 不存在", "结构", "skill 无法正常读取，当前不可用")
        ], 0)
    try:
        content = skill_md.read_text(encoding='utf-8')
    except Exception as e:
        return finalize([
            issue("blocking", "error", f"无法读取: {e}", "结构", "skill 无法正常读取，当前不可用")
        ], 0)

    issues, deductions = [], 0
    fm = parse_frontmatter(content)
    if not fm.get('name'):
        issues.append(issue("blocking", "error", "frontmatter 缺少 name", "结构", "难以稳定识别 skill 身份，后续治理和展示会混乱"))
        deductions += 15
    desc = fm.get('description', '')
    if not desc:
        issues.append(issue("blocking", "error", "frontmatter 缺少 description", "触发", "会直接削弱 skill 被正确触发和理解的概率"))
        deductions += 20
    elif len(desc) < 50:
        issues.append(issue("risk", "warning", f"description 过短（{len(desc)}字）", "触发", "触发条件和适用边界不清，容易误用或漏用"))
        deductions += 10
    if desc and not re.search(r'[\u4e00-\u9fff]', desc):
        issues.append(issue("risk", "warning", "description 缺少中文触发词", "触发", "中文场景下触发稳定性会下降"))
        deductions += 8
    if not (skill_dir / "README.md").exists():
        issues.append(issue("optimization", "info", "缺少 README.md", "文档", "不影响当前使用，但后续维护和交接成本更高"))
        deductions += 5
    workflow_pattern = r'(Phase|Step|步骤|阶段)\s*\d|Default Workflow|默认工作流|默认流程|Visible Progress Plan'
    if not re.search(workflow_pattern, content, re.I) and len(content) > 500:
        issues.append(issue("optimization", "info", "未发现工作流结构", "工作流", "不影响能用，但不利于后续测试、拆解和自动演进"))
        deductions += 5
    if not re.search(r'(fallback|错误|异常|失败|error|fail)', content, re.I):
        issues.append(issue("risk", "warning", "缺少异常处理路径", "鲁棒性", "边界情况更容易跑偏，自动化效果会变差"))
        deductions += 8
    if len(content) < 200:
        issues.append(issue("risk", "warning", f"内容过短（{len(content)}字节）", "完整性", "规则表达可能不完整，输出稳定性不足"))
        deductions += 10
    for ref in re.findall(r'`([^`]+\.(?:py|sh|json|yaml|yml))`', content):
        if ref.startswith(('/', '~')) or is_generated_or_placeholder_ref(ref):
            continue
        if not referenced_file_exists(skill_dir, ref):
            issues.append(issue("blocking", "error", f"引用文件不存在: {ref}", "依赖", "文档与实际文件不一致，按说明执行会直接失败"))
            deductions += 10

    score = max(0, 100 - deductions)
    return finalize(issues, score)

def load_meta(skill_dir: Path) -> dict:
    f = get_skill_state_dir(skill_dir) / "meta.json"
    legacy = skill_dir / ".skill-meta.json"
    source = f if f.exists() else legacy
    if source.exists():
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
            if source == legacy and not f.exists():
                save_meta(skill_dir, data)
            return data
        except: pass
    return {}

def save_meta(skill_dir: Path, meta: dict):
    state_dir = ensure_skill_state_dir(skill_dir)
    (state_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

def get_skill_mtime_iso(skill_md: Path) -> str:
    return datetime.fromtimestamp(skill_md.stat().st_mtime).isoformat()

def extract_section(content: str, headings: list[str]) -> str:
    lines = content.splitlines()
    for idx, line in enumerate(lines):
        if any(h in line for h in headings):
            collected = []
            for inner in lines[idx + 1:]:
                if inner.startswith("#"):
                    break
                if inner.strip():
                    collected.append(inner.strip())
            if collected:
                return "\n".join(collected[:8])
    return ""

def summarize_description(desc: str) -> str:
    return (desc or "").strip()[:160]

def extract_overview_from_skill(content: str, fm: dict) -> dict:
    description = summarize_description(fm.get("description", ""))
    usage = extract_section(content, ["如何使用", "使用方式", "用法", "使用方法"])
    scenarios = extract_section(content, ["推荐场景", "适用场景", "使用场景", "触发"])
    cautions = extract_section(content, ["注意事项", "限制", "边界", "异常", "失败", "fallback"])

    items = {
        "summary": description,
        "usage": usage,
        "recommended_scenarios": scenarios,
        "cautions": cautions,
    }
    missing = [k for k, v in items.items() if not v]
    items["complete"] = len(missing) == 0
    items["missing"] = missing
    return items

def generate_overview_with_ai(content: str, fm: dict) -> dict:
    result = ollama_generate_json(f"""阅读下面的 SKILL.md，输出 JSON：
{{
  "summary":"一句话介绍 skill 做什么",
  "usage":["如何使用要点1","如何使用要点2","如何使用要点3"],
  "recommended_scenarios":["推荐场景1","推荐场景2","推荐场景3"],
  "cautions":["注意事项1","注意事项2","注意事项3"]
}}
只返回 JSON。数组最多 3 条，每条一句话，简洁明确。

SKILL.md:
{content[:4000]}""")
    return {
        "summary": str(result.get("summary", "") or summarize_description(fm.get("description", ""))),
        "usage": [str(x) for x in result.get("usage", [])[:3]],
        "recommended_scenarios": [str(x) for x in result.get("recommended_scenarios", [])[:3]],
        "cautions": [str(x) for x in result.get("cautions", [])[:3]],
        "source": "ai",
    }

def build_overview_summary(skill_dir: Path, force_refresh: bool = False) -> dict:
    skill_md = skill_dir / "SKILL.md"
    content = skill_md.read_text(encoding="utf-8")
    fm = parse_frontmatter(content)
    meta = load_meta(skill_dir)
    skill_mtime = get_skill_mtime_iso(skill_md)
    cached = meta.get("overview_summary")

    if not force_refresh and cached and cached.get("skill_mtime") == skill_mtime:
        return cached

    extracted = extract_overview_from_skill(content, fm)
    summary = {
        "summary": extracted["summary"],
        "usage": [extracted["usage"]] if extracted["usage"] else [],
        "recommended_scenarios": [extracted["recommended_scenarios"]] if extracted["recommended_scenarios"] else [],
        "cautions": [extracted["cautions"]] if extracted["cautions"] else [],
        "source": "rule",
        "generated_at": datetime.now().isoformat(),
        "skill_mtime": skill_mtime,
    }

    if extracted["summary"] and extracted["usage"] and extracted["recommended_scenarios"] and extracted["cautions"] and not force_refresh:
        meta["overview_summary"] = summary
        save_meta(skill_dir, meta)
        return summary

    try:
        ai_summary = generate_overview_with_ai(content, fm)
        merged = {
            "summary": ai_summary["summary"] or summary["summary"],
            "usage": summary["usage"] or ai_summary["usage"],
            "recommended_scenarios": summary["recommended_scenarios"] or ai_summary["recommended_scenarios"],
            "cautions": summary["cautions"] or ai_summary["cautions"],
            "source": "hybrid" if any(summary[k] for k in ("usage", "recommended_scenarios", "cautions")) else "ai",
            "generated_at": datetime.now().isoformat(),
            "skill_mtime": skill_mtime,
        }
    except Exception:
        merged = summary
    meta["overview_summary"] = merged
    save_meta(skill_dir, meta)
    return merged

def strip_code_fence(text: str) -> str:
    text = re.sub(r'^```(?:json|markdown|md)?\n?', '', text.strip())
    text = re.sub(r'\n?```$', '', text)
    return text.strip()

def get_ollama_base_url() -> str:
    return (os.environ.get("OLLAMA_BASE_URL") or "http://127.0.0.1:11434").rstrip("/")

def get_ollama_model() -> str:
    return os.environ.get("OLLAMA_MODEL") or "glm4:latest"

def get_ai_provider() -> str:
    return (os.environ.get("AI_PROVIDER") or "auto").strip().lower()

def get_anthropic_model() -> str:
    return os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-4-6"

def ollama_available() -> bool:
    import httpx

    try:
        with httpx.Client(timeout=3, trust_env=False) as client:
            resp = client.get(f"{get_ollama_base_url()}/api/tags")
        resp.raise_for_status()
        data = resp.json()
        names = {m.get("name", "") for m in data.get("models", [])}
        return get_ollama_model() in names
    except Exception:
        return False

def resolve_ai_provider() -> str:
    provider = get_ai_provider()
    if provider in {"ollama", "anthropic"}:
        return provider
    if ollama_available():
        return "ollama"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    raise RuntimeError("没有可用的 AI provider。请启动 Ollama，或设置 ANTHROPIC_API_KEY。")

def anthropic_generate_text(prompt: str, max_tokens: int, system: str | None = None) -> str:
    import anthropic as ac

    client = ac.Anthropic()
    kwargs = {
        "model": get_anthropic_model(),
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system
    resp = client.messages.create(**kwargs)
    return resp.content[0].text.strip()

def ollama_generate_text(prompt: str, max_tokens: int, system: str | None = None,
                         json_mode: bool = False) -> str:
    import httpx

    final_prompt = prompt if not system else f"{system}\n\n用户请求：\n{prompt}"
    payload = {
        "model": get_ollama_model(),
        "prompt": final_prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": max_tokens},
    }
    if json_mode:
        payload["format"] = "json"

    with httpx.Client(timeout=120, trust_env=False) as client:
        resp = client.post(f"{get_ollama_base_url()}/api/generate", json=payload)
    resp.raise_for_status()
    return resp.json().get("response", "").strip()

def ai_generate_text(prompt: str, max_tokens: int = 2000, system: str | None = None,
                     json_mode: bool = False) -> str:
    provider = resolve_ai_provider()
    if provider == "ollama":
        return ollama_generate_text(prompt, max_tokens=max_tokens, system=system, json_mode=json_mode)
    return anthropic_generate_text(prompt, max_tokens=max_tokens, system=system)

def normalize_skill_type(raw: str, reason: str = "", summary: str = "") -> str:
    raw = (raw or "").strip().lower()
    text = f"{raw} {reason} {summary}"
    if raw in {"verifiable", "anchor", "judgment"}:
        return raw
    if "verifiable" in raw or "可验证" in text:
        return "verifiable"
    if "anchor" in raw or "锚点" in text or "人工审批" in text or "样本" in text:
        return "anchor"
    if "judgment" in raw or "判断" in text or "主观" in text or "风格" in text:
        return "judgment"
    return "verifiable"

def normalize_analysis_result(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("AI 分析返回格式不是 JSON 对象")
    reason = str(data.get("type_reason", "") or "")
    summary = str(data.get("summary", "") or "")
    return {
        "skill_type": normalize_skill_type(str(data.get("skill_type", "") or ""), reason, summary),
        "type_reason": reason,
        "top_issues": data.get("top_issues", [])[:3] if isinstance(data.get("top_issues"), list) else [],
        "top_suggestions": data.get("top_suggestions", [])[:3] if isinstance(data.get("top_suggestions"), list) else [],
        "summary": summary,
    }

def ollama_generate_json(prompt: str) -> dict:
    return json.loads(strip_code_fence(ai_generate_text(prompt, max_tokens=2000, json_mode=True)))

def scan_skills(path: Path) -> list:
    if not path.exists(): return []
    skills = []
    for d in sorted(path.iterdir()):
        if not d.is_dir() or not (d / "SKILL.md").exists(): continue
        try:
            content = (d / "SKILL.md").read_text(encoding='utf-8')
            fm = parse_frontmatter(content)
            stat = (d / "SKILL.md").stat()
            meta = load_meta(d)
            health = check_health(d)
            skills.append({
                "id": d.name, "name": fm.get('name', d.name),
                "description": (fm.get('description', '') or '')[:120],
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d'),
                "has_readme": (d / "README.md").exists(),
                "type": meta.get('type', 'unknown'),
                "health_score": health["score"], "health_grade": health["grade"],
                "issue_count": len(health["issues"]),
                "blocking_count": health["counts"]["blocking"],
                "risk_count": health["counts"]["risk"],
                "optimization_count": health["counts"]["optimization"],
                "has_tests": has_test_cases(d),
                "write_protected": is_write_protected_skill(d),
            })
        except Exception as e:
            skills.append({"id": d.name, "name": d.name, "error": str(e),
                           "type": "unknown", "health_score": 0,
                           "health_grade": "F", "issue_count": 1,
                           "blocking_count": 1, "risk_count": 0,
                           "optimization_count": 0, "has_tests": False})
    return skills

# ── Validators ──────────────────────────────────────────────
def run_validator(output: str, v: dict) -> tuple:
    t = v.get('type')
    if t == 'contains':
        val = v.get('value', '')
        ok = val.lower() in output.lower()
        return ok, (f"包含 '{val}'" if ok else f"未找到 '{val}'")
    if t == 'not_contains':
        val = v.get('value', '')
        ok = val.lower() not in output.lower()
        return ok, (f"不含 '{val}'" if ok else f"意外包含 '{val}'")
    if t == 'regex':
        pat = v.get('pattern', '')
        ok = bool(re.search(pat, output, re.I | re.S))
        return ok, (f"匹配 {pat}" if ok else f"未匹配 {pat}")
    if t == 'json_valid':
        try: json.loads(output); return True, "有效 JSON"
        except: return False, "无效 JSON"
    if t == 'min_length':
        mn = v.get('value', 0)
        ok = len(output) >= mn
        return ok, (f"长度 {len(output)} ≥ {mn}" if ok else f"长度 {len(output)} < {mn}")
    if t == 'length_range':
        mn, mx = v.get('min', 0), v.get('max', 999999)
        ok = mn <= len(output) <= mx
        return ok, (f"长度 {len(output)} OK" if ok else f"长度 {len(output)} 超出 [{mn},{mx}]")
    return False, f"未知验证器: {t}"

def run_test_case(skill_content: str, case: dict) -> dict:
    system = f"你是一个 AI 助手。以下是你需要遵循的操作指南：\n\n{skill_content}\n\n严格按照上述指南执行任务。"
    try:
        output = ai_generate_text(case["prompt"], max_tokens=2000, system=system)
    except Exception as e:
        return {"case_id": case["id"], "name": case.get("name", ""),
                "error": str(e), "passed": 0,
                "total": len(case.get("validators", [])), "score": 0.0, "details": []}

    validators = case.get("validators", [])
    details = []
    for vld in validators:
        ok, reason = run_validator(output, vld)
        details.append({"type": vld["type"], "passed": ok, "reason": reason})

    passed = sum(1 for d in details if d["passed"])
    total = len(validators)
    return {
        "case_id": case["id"], "name": case.get("name", ""),
        "output_preview": output[:300],
        "passed": passed, "total": total,
        "score": passed / total if total > 0 else 1.0,
        "details": details
    }

def compute_skill_score(results: list) -> float:
    if not results: return 0.0
    return sum(r.get("score", 0) for r in results) / len(results)

# ── Version control ─────────────────────────────────────────
def get_versions_dir(skill_dir: Path) -> Path:
    return get_skill_state_dir(skill_dir) / "versions"

def get_version_index_file(skill_dir: Path) -> Path:
    return get_versions_dir(skill_dir) / "index.json"

def load_version_index(skill_dir: Path) -> dict:
    index_file = get_version_index_file(skill_dir)
    if index_file.exists():
        try:
            return json.loads(index_file.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_version_index(skill_dir: Path, index: dict):
    vdir = ensure_skill_state_dir(skill_dir) / "versions"
    vdir.mkdir(exist_ok=True)
    get_version_index_file(skill_dir).write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

def save_version(skill_dir: Path, label: str = "", source: str = "manual",
                 score: float | None = None, note: str = "") -> str:
    return save_version_content(
        skill_dir,
        (skill_dir / "SKILL.md").read_text(encoding="utf-8"),
        label=label,
        source=source,
        score=score,
        note=note,
    )

def save_version_content(skill_dir: Path, content: str, label: str = "", source: str = "manual",
                         score: float | None = None, note: str = "") -> str:
    vdir = ensure_skill_state_dir(skill_dir) / "versions"
    vdir.mkdir(exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    vid = f"{ts}-{label}" if label else ts
    target = vdir / f"{vid}.md"
    target.write_text(content, encoding="utf-8")
    index = load_version_index(skill_dir)
    index[vid] = {
        "id": vid,
        "created_at": datetime.now().isoformat(),
        "modified": datetime.fromtimestamp(target.stat().st_mtime).isoformat(),
        "size": target.stat().st_size,
        "source": source,
        "score": round(score, 4) if score is not None else None,
        "note": note,
    }
    save_version_index(skill_dir, index)
    return vid

def list_versions(skill_dir: Path) -> list:
    vdir = get_versions_dir(skill_dir)
    if not vdir.exists(): return []
    index = load_version_index(skill_dir)
    meta = load_meta(skill_dir)
    baseline_id = meta.get("baseline_version_id")
    items = []
    for f in sorted(vdir.glob("*.md"), reverse=True):
        entry = index.get(f.stem, {})
        items.append({
            "id": f.stem,
            "modified": entry.get("modified") or datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            "created_at": entry.get("created_at") or datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            "size": entry.get("size") or f.stat().st_size,
            "source": entry.get("source", "manual"),
            "score": entry.get("score"),
            "note": entry.get("note", ""),
            "is_baseline": f.stem == baseline_id,
        })
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return items

def get_version_content(skill_dir: Path, version_id: str) -> str | None:
    src = get_versions_dir(skill_dir) / f"{version_id}.md"
    if not src.exists():
        return None
    return src.read_text(encoding="utf-8")

def restore_version(skill_dir: Path, version_id: str) -> bool:
    src = get_versions_dir(skill_dir) / f"{version_id}.md"
    if not src.exists(): return False
    shutil.copy2(src, skill_dir / "SKILL.md")
    return True

def create_pre_restore_snapshot(skill_dir: Path) -> str:
    return save_version(skill_dir, "pre-restore", source="pre-restore", note="恢复基线前的保险快照")

def create_pre_apply_candidate_snapshot(skill_dir: Path) -> str:
    return save_version(skill_dir, "pre-apply-candidate", source="pre-apply-candidate", note="应用候选版本前的保险快照")

def build_diff_blocks(old_text: str, new_text: str) -> list[dict]:
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    matcher = SequenceMatcher(a=old_lines, b=new_lines)
    blocks = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        block_type = {"insert": "added", "delete": "deleted", "replace": "modified"}[tag]
        blocks.append({
            "type": block_type,
            "old_start": i1 + 1,
            "old_end": i2,
            "new_start": j1 + 1,
            "new_end": j2,
            "old_lines": old_lines[i1:i2],
            "new_lines": new_lines[j1:j2],
            "line_count": max(i2 - i1, j2 - j1),
        })
    return blocks

def append_evolution_log(skill_dir: Path, entry: dict):
    state_dir = ensure_skill_state_dir(skill_dir)
    with open(state_dir / "evolution-log.jsonl", 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')

def build_baseline_status(skill_dir: Path, meta: dict) -> dict:
    baseline_id = meta.get("baseline_version_id")
    versions = {v["id"]: v for v in list_versions(skill_dir)}
    baseline = versions.get(baseline_id) if baseline_id else None
    return {
        "exists": baseline is not None,
        "version_id": baseline_id,
        "score": meta.get("baseline_score"),
        "set_at": meta.get("baseline_set_at"),
        "version": baseline,
    }

def record_last_test(skill_dir: Path, score: float, results: list):
    meta = load_meta(skill_dir)
    meta["last_score"] = round(score, 4)
    meta["last_tested"] = datetime.now().isoformat()
    meta["last_test_results"] = {
        "score": round(score, 4),
        "tested_at": meta["last_tested"],
        "results": results,
    }
    save_meta(skill_dir, meta)

# ── Evolution engine ─────────────────────────────────────────
def propose_improvement(skill_content: str, test_results: list, round_num: int) -> str:
    failed = [r for r in test_results if r.get("score", 1) < 1.0]
    failed_summary = ""
    for r in failed:
        failed_summary += f"\n测试「{r.get('name', r['case_id'])}」得分 {r['score']:.0%}：\n"
        for d in r.get("details", []):
            if not d["passed"]:
                failed_summary += f"  - 失败: {d['reason']}\n"

    proposed = ai_generate_text(f"""你是一个 AI Skill 优化专家。请对以下 SKILL.md 提出一个具体改进。

规则：
- 只改一个地方（一段指令/一个步骤/一段描述）
- 不改 skill 的核心功能
- 不引入新依赖文件
- 优化后文件不超过原来的 150%

当前测试失败情况：
{failed_summary if failed_summary else "所有测试通过，尝试优化指令清晰度和边界处理"}

第 {round_num} 轮，请针对失败情况提出有效改进。

直接返回完整修改后的 SKILL.md 内容，不要任何解释或 markdown 代码块。

当前 SKILL.md：
{skill_content}""", max_tokens=4000)
    proposed = re.sub(r'^```(?:markdown|md)?\n?', '', proposed)
    proposed = re.sub(r'\n?```$', '', proposed)
    return proposed.strip()

def evolution_stream(skill_dir: Path, max_rounds: int, confirm_write: bool = False) -> Generator:
    def event(data: dict) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    skill_md = skill_dir / "SKILL.md"
    test_cases_file = get_test_cases_file(skill_dir)
    write_protected = is_write_protected_skill(skill_dir) and not confirm_write

    if not test_cases_file.exists():
        yield event({"type": "error", "message": "未找到 test-cases.json，请先添加测试用例"})
        return
    try:
        test_cases = json.loads(test_cases_file.read_text())["cases"]
    except Exception as e:
        yield event({"type": "error", "message": f"测试用例格式错误: {e}"}); return
    if not test_cases:
        yield event({"type": "error", "message": "测试用例为空"}); return

    yield event({
        "type": "start",
        "message": f"开始进化｜{len(test_cases)} 个测试用例｜最多 {max_rounds} 轮",
        "write_protection": write_protection_status(skill_dir),
        "candidate_only": write_protected,
    })
    if write_protected:
        yield event({
            "type": "write_protected",
            "message": "当前是外部安装 skill，本次只保存候选版本，不覆盖真实 SKILL.md。"
        })

    # Baseline
    yield event({"type": "phase", "phase": "baseline", "message": "运行基线测试..."})
    current_content = skill_md.read_text(encoding='utf-8')
    baseline_results = []
    for tc in test_cases:
        yield event({"type": "testing", "case": tc.get("name", tc["id"])})
        result = run_test_case(current_content, tc)
        baseline_results.append(result)
        yield event({"type": "test_result", "case_id": tc["id"],
                     "name": tc.get("name", tc["id"]),
                     "score": result["score"], "passed": result["passed"],
                     "total": result["total"], "details": result.get("details", [])})

    baseline_score = compute_skill_score(baseline_results)
    save_version(skill_dir, "baseline", source="evolution-baseline", score=baseline_score)
    best_score = baseline_score
    current_results = baseline_results
    no_improve = 0

    yield event({"type": "baseline_done", "score": baseline_score,
                 "message": f"基线分数: {baseline_score:.1%}"})

    # Evolution rounds
    for round_num in range(1, max_rounds + 1):
        yield event({"type": "round_start", "round": round_num,
                     "message": f"第 {round_num} 轮：生成改进方案..."})
        try:
            proposed = propose_improvement(current_content, current_results, round_num)
        except Exception as e:
            yield event({"type": "error", "message": f"改进方案生成失败: {e}"}); break

        if proposed == current_content:
            yield event({"type": "converged", "message": "内容无变化，已收敛"}); break

        old_lines = set(current_content.splitlines())
        new_lines = set(proposed.splitlines())
        yield event({"type": "proposal", "round": round_num,
                     "diff": f"+{len(new_lines-old_lines)} -{len(old_lines-new_lines)} 行"})

        yield event({"type": "phase", "phase": "testing", "message": "测试改进方案..."})
        new_results = []
        for tc in test_cases:
            yield event({"type": "testing", "case": tc.get("name", tc["id"])})
            result = run_test_case(proposed, tc)
            new_results.append(result)
            yield event({"type": "test_result", "case_id": tc["id"],
                         "name": tc.get("name", tc["id"]),
                         "score": result["score"], "passed": result["passed"],
                         "total": result["total"], "details": result.get("details", [])})

        new_score = compute_skill_score(new_results)
        improved = new_score > best_score

        append_evolution_log(skill_dir, {
            "timestamp": datetime.now().isoformat(), "round": round_num,
            "old_score": round(best_score, 4), "new_score": round(new_score, 4),
            "decision": "candidate" if improved and write_protected else "keep" if improved else "revert",
            "delta": round(new_score - best_score, 4)
        })

        if improved:
            if write_protected:
                save_version_content(
                    skill_dir,
                    proposed,
                    f"r{round_num}-candidate",
                    source="evolution-candidate",
                    score=new_score,
                    note="外部 skill 写保护：仅保存候选版本，未覆盖 SKILL.md",
                )
            else:
                save_version_content(skill_dir, proposed, f"r{round_num}-keep", source="evolution-keep", score=new_score)
                skill_md.write_text(proposed, encoding='utf-8')
            best_score = new_score
            current_content = proposed
            current_results = new_results
            no_improve = 0
            decision = "candidate" if write_protected else "keep"
            message = f"候选已保存 → {new_score:.1%}" if write_protected else f"✓ 保留 → {new_score:.1%}"
            yield event({"type": "round_done", "round": round_num, "decision": decision,
                         "old_score": round(best_score - (new_score - best_score), 4),
                         "new_score": round(new_score, 4),
                         "write_protected": write_protected,
                         "message": message})
        else:
            no_improve += 1
            save_version_content(skill_dir, proposed, f"r{round_num}-revert", source="evolution-revert", score=new_score)
            yield event({"type": "round_done", "round": round_num, "decision": "revert",
                         "old_score": round(best_score, 4), "new_score": round(new_score, 4),
                         "message": f"✗ 回滚（{new_score:.1%} 未超过 {best_score:.1%}）"})
            if no_improve >= 2:
                yield event({"type": "converged", "message": "连续 2 轮无改进，已收敛"}); break

    yield event({"type": "done", "final_score": round(best_score, 4),
                 "message": f"进化完成｜最终分数 {best_score:.1%}"})

# ── Routes ──────────────────────────────────────────────────
@app.route('/')
def index(): return send_from_directory('static', 'index.html')

@app.route('/api/config')
def config():
    p = get_skills_path()
    try:
        provider = resolve_ai_provider()
        model = get_ollama_model() if provider == "ollama" else get_anthropic_model()
    except Exception:
        provider = get_ai_provider()
        model = get_ollama_model() if provider == "ollama" else get_anthropic_model()
    return jsonify({
        "skills_path": str(p),
        "meta_path": str(get_manager_meta_root()),
        "exists": p.exists(),
        "ai_provider": provider,
        "ai_model": model,
    })

@app.route('/api/skills')
def list_skills():
    p = get_skills_path()
    skills = scan_skills(p)
    return jsonify({"skills": skills, "total": len(skills), "path": str(p)})

@app.route('/api/skills/<skill_id>')
def get_skill(skill_id):
    skill_dir = get_skills_path() / skill_id
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists(): return jsonify({"error": "Not found"}), 404
    content = skill_md.read_text(encoding='utf-8')
    fm = parse_frontmatter(content)
    meta = load_meta(skill_dir)
    health = check_health(skill_dir)
    baseline = build_baseline_status(skill_dir, meta)
    overview_summary = build_overview_summary(skill_dir)
    last_test = meta.get("last_test_results")
    delta = None
    if baseline.get("score") is not None and last_test and last_test.get("score") is not None:
        delta = round(last_test["score"] - baseline["score"], 4)
    return jsonify({
        "id": skill_id, "name": fm.get('name', skill_id),
        "description": fm.get('description', ''),
        "health": health, "type": meta.get('type', 'unknown'),
        "modified": datetime.fromtimestamp(skill_md.stat().st_mtime).isoformat(),
        "baseline": baseline,
        "last_test": last_test,
        "delta_from_baseline": delta,
        "overview_summary": overview_summary,
        "write_protection": write_protection_status(skill_dir),
    })

@app.route('/api/skills/<skill_id>/type', methods=['PUT'])
def update_type(skill_id):
    skill_dir = get_skills_path() / skill_id
    if not skill_dir.exists(): return jsonify({"error": "Not found"}), 404
    meta = load_meta(skill_dir)
    meta['type'] = request.get_json()['type']
    save_meta(skill_dir, meta)
    return jsonify({"success": True})

@app.route('/api/skills/<skill_id>/ai-analyze', methods=['POST'])
def ai_analyze(skill_id):
    skill_dir = get_skills_path() / skill_id
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists(): return jsonify({"error": "Not found"}), 404
    content = skill_md.read_text(encoding='utf-8')
    try:
        result = ollama_generate_json(f"""分析这个 SKILL.md，用 JSON 格式回复：
{{"skill_type":"只能填写 verifiable、anchor、judgment 三选一","type_reason":"分类理由",
"top_issues":["问题1","问题2","问题3"],"top_suggestions":["建议1","建议2","建议3"],
"summary":"总体评价两句话"}}
只返回 JSON。
skill_type 只能是 verifiable、anchor、judgment 三选一，不能返回解释文本，不能返回带 | 的占位字符串。
SKILL.md:
{content[:3000]}""")
        return jsonify(normalize_analysis_result(result))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Evolution
@app.route('/api/skills/<skill_id>/evolve/tests', methods=['GET'])
def get_tests(skill_id):
    f = get_test_cases_file(get_skills_path() / skill_id)
    if not f.exists(): return jsonify({"cases": []})
    try: return jsonify(json.loads(f.read_text()))
    except: return jsonify({"cases": []})

@app.route('/api/skills/<skill_id>/evolve/tests', methods=['PUT'])
def save_tests(skill_id):
    skill_dir = get_skills_path() / skill_id
    if not skill_dir.exists(): return jsonify({"error": "Not found"}), 404
    get_test_cases_file(skill_dir, for_write=True).write_text(
        json.dumps(request.get_json(), ensure_ascii=False, indent=2), encoding="utf-8")
    return jsonify({"success": True})

@app.route('/api/skills/<skill_id>/evolve/generate-tests', methods=['POST'])
def generate_tests(skill_id):
    skill_dir = get_skills_path() / skill_id
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists(): return jsonify({"error": "Not found"}), 404
    content = skill_md.read_text(encoding='utf-8')
    try:
        cases = ollama_generate_json(f"""根据这个 SKILL.md，生成 2-3 个测试用例。

可用 validator 类型：
- contains: {{"type":"contains","value":"..."}}
- not_contains: {{"type":"not_contains","value":"..."}}
- min_length: {{"type":"min_length","value":100}}
- json_valid: {{"type":"json_valid"}}
- regex: {{"type":"regex","pattern":"..."}}

返回 JSON：{{"cases":[{{"id":"tc1","name":"测试名","prompt":"用户输入","validators":[...]}}]}}
只返回 JSON。

SKILL.md:
{content[:2500]}""")
        get_test_cases_file(skill_dir, for_write=True).write_text(
            json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
        return jsonify(cases)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/skills/<skill_id>/evolve/run-tests', methods=['POST'])
def run_tests(skill_id):
    skill_dir = get_skills_path() / skill_id
    skill_md = skill_dir / "SKILL.md"
    test_cases_file = get_test_cases_file(skill_dir)
    if not skill_md.exists(): return jsonify({"error": "Not found"}), 404
    if not test_cases_file.exists(): return jsonify({"error": "No test cases"}), 400
    content = skill_md.read_text(encoding='utf-8')
    cases = json.loads(test_cases_file.read_text())["cases"]
    results = [run_test_case(content, tc) for tc in cases]
    overall_score = compute_skill_score(results)
    record_last_test(skill_dir, overall_score, results)
    meta = load_meta(skill_dir)
    baseline_score = meta.get("baseline_score")
    delta = round(overall_score - baseline_score, 4) if baseline_score is not None else None
    return jsonify({
        "results": results,
        "overall_score": overall_score,
        "baseline_score": baseline_score,
        "delta_from_baseline": delta,
    })

@app.route('/api/skills/<skill_id>/evolve/start')
def start_evolution(skill_id):
    skill_dir = get_skills_path() / skill_id
    if not skill_dir.exists(): return jsonify({"error": "Not found"}), 404
    max_rounds = int(request.args.get('rounds', 5))
    confirm_write = request_confirmed_write()

    def generate():
        try:
            for event in evolution_stream(skill_dir, max_rounds, confirm_write=confirm_write):
                yield event
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','message':str(e)})}\n\n"

    return Response(stream_with_context(generate()),
                    mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

@app.route('/api/skills/<skill_id>/evolve/history')
def get_history(skill_id):
    skill_dir = get_skills_path() / skill_id
    return jsonify({"versions": list_versions(skill_dir)})

@app.route('/api/skills/<skill_id>/evolve/restore/<version_id>', methods=['POST'])
def restore(skill_id, version_id):
    skill_dir = get_skills_path() / skill_id
    if not skill_dir.exists(): return jsonify({"error": "Not found"}), 404
    if is_write_protected_skill(skill_dir) and not request_confirmed_write():
        return write_protection_error(skill_dir)
    create_pre_restore_snapshot(skill_dir)
    ok = restore_version(skill_dir, version_id)
    return jsonify({"success": True} if ok else {"error": "Version not found"}), (200 if ok else 404)

@app.route('/api/skills/<skill_id>/evolve/candidate/<version_id>/diff')
def candidate_diff(skill_id, version_id):
    skill_dir = get_skills_path() / skill_id
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists(): return jsonify({"error": "Not found"}), 404
    candidate_content = get_version_content(skill_dir, version_id)
    if candidate_content is None:
        return jsonify({"error": "Candidate version not found"}), 404
    versions = {v["id"]: v for v in list_versions(skill_dir)}
    version = versions.get(version_id, {})
    if version.get("source") != "evolution-candidate":
        return jsonify({"error": "Version is not an evolution candidate"}), 400
    current_content = skill_md.read_text(encoding="utf-8")
    blocks = build_diff_blocks(current_content, candidate_content)
    return jsonify({
        "candidate_version_id": version_id,
        "version": version,
        "blocks": blocks,
        "summary": {
            "added": sum(1 for b in blocks if b["type"] == "added"),
            "deleted": sum(1 for b in blocks if b["type"] == "deleted"),
            "modified": sum(1 for b in blocks if b["type"] == "modified"),
        }
    })

@app.route('/api/skills/<skill_id>/evolve/candidate/<version_id>/apply', methods=['POST'])
def apply_candidate(skill_id, version_id):
    skill_dir = get_skills_path() / skill_id
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists(): return jsonify({"error": "Not found"}), 404
    if is_write_protected_skill(skill_dir) and not request_confirmed_write():
        return write_protection_error(skill_dir)
    versions = {v["id"]: v for v in list_versions(skill_dir)}
    version = versions.get(version_id)
    if not version:
        return jsonify({"error": "Candidate version not found"}), 404
    if version.get("source") != "evolution-candidate":
        return jsonify({"error": "Version is not an evolution candidate"}), 400
    candidate_content = get_version_content(skill_dir, version_id)
    if candidate_content is None:
        return jsonify({"error": "Candidate version not found"}), 404
    snapshot_id = create_pre_apply_candidate_snapshot(skill_dir)
    skill_md.write_text(candidate_content, encoding="utf-8")
    return jsonify({"success": True, "version_id": version_id, "pre_apply_version_id": snapshot_id})

@app.route('/api/skills/<skill_id>/baseline/restore', methods=['POST'])
def restore_baseline(skill_id):
    skill_dir = get_skills_path() / skill_id
    if not skill_dir.exists(): return jsonify({"error": "Not found"}), 404
    meta = load_meta(skill_dir)
    baseline_id = meta.get("baseline_version_id")
    if not baseline_id:
        return jsonify({"error": "No baseline"}), 400
    if is_write_protected_skill(skill_dir) and not request_confirmed_write():
        return write_protection_error(skill_dir)
    create_pre_restore_snapshot(skill_dir)
    ok = restore_version(skill_dir, baseline_id)
    return jsonify({"success": True, "version_id": baseline_id} if ok else {"error": "Baseline version not found"}), (200 if ok else 404)

# ── Baseline ─────────────────────────────────────────────────
@app.route('/api/skills/<skill_id>/evolve/set-baseline', methods=['POST'])
def set_baseline(skill_id):
    """Run tests and store the current skill as the baseline snapshot."""
    skill_dir = get_skills_path() / skill_id
    skill_md = skill_dir / "SKILL.md"
    test_file = get_test_cases_file(skill_dir)
    if not skill_md.exists(): return jsonify({"error": "Not found"}), 404
    if not test_file.exists(): return jsonify({"error": "No test cases"}), 400

    content = skill_md.read_text(encoding='utf-8')
    cases = json.loads(test_file.read_text())["cases"]
    results = [run_test_case(content, tc) for tc in cases]
    score = compute_skill_score(results)

    meta = load_meta(skill_dir)
    version_id = save_version(skill_dir, "baseline", source="baseline", score=score, note="用户手动保存为基线")
    meta["baseline_version_id"] = version_id
    meta["baseline_score"] = round(score, 4)
    meta["baseline_set_at"] = datetime.now().isoformat()
    save_meta(skill_dir, meta)
    record_last_test(skill_dir, score, results)

    return jsonify({"score": score, "results": results, "version_id": version_id})

@app.route('/api/skills/<skill_id>/summary/regenerate', methods=['POST'])
def regenerate_summary(skill_id):
    skill_dir = get_skills_path() / skill_id
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists(): return jsonify({"error": "Not found"}), 404
    summary = build_overview_summary(skill_dir, force_refresh=True)
    return jsonify({"summary": summary})

@app.route('/api/skills/<skill_id>/baseline/diff')
def baseline_diff(skill_id):
    skill_dir = get_skills_path() / skill_id
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists(): return jsonify({"error": "Not found"}), 404
    meta = load_meta(skill_dir)
    baseline_id = meta.get("baseline_version_id")
    if not baseline_id:
        return jsonify({"error": "No baseline"}), 400
    baseline_content = get_version_content(skill_dir, baseline_id)
    if baseline_content is None:
        return jsonify({"error": "Baseline version not found"}), 404
    current_content = skill_md.read_text(encoding="utf-8")
    blocks = build_diff_blocks(baseline_content, current_content)
    return jsonify({
        "baseline_version_id": baseline_id,
        "blocks": blocks,
        "summary": {
            "added": sum(1 for b in blocks if b["type"] == "added"),
            "deleted": sum(1 for b in blocks if b["type"] == "deleted"),
            "modified": sum(1 for b in blocks if b["type"] == "modified"),
        }
    })

# ── Notifications SSE ─────────────────────────────────────────
@app.route('/api/notifications')
def notifications():
    """Browser subscribes here to receive real-time file-change events."""
    q: queue.Queue = queue.Queue(maxsize=50)
    with _notification_lock:
        _notification_clients.append(q)

    def generate():
        # Send a heartbeat immediately so browser knows connection is live
        yield "data: {\"type\":\"connected\"}\n\n"
        try:
            while True:
                try:
                    data = q.get(timeout=20)
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    yield ": heartbeat\n\n"   # SSE comment keeps connection alive
        except GeneratorExit:
            pass
        finally:
            with _notification_lock:
                if q in _notification_clients:
                    _notification_clients.remove(q)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )

if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("APP_PORT", 7890))
    host = os.environ.get("APP_HOST", "0.0.0.0")
    print(f"\n  Skills Manager  →  http://{host}:{port}\n")
    start_watcher()
    app.run(host=host, port=port, debug=False, use_reloader=False)

#!/usr/bin/env python3
"""Skills Manager - Web interface for managing and evolving AI skills"""

from flask import Flask, jsonify, request, send_from_directory, Response, stream_with_context
from flask_cors import CORS
import os, re, json, yaml, shutil, threading, time, queue
from pathlib import Path
from datetime import datetime
from typing import Generator

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
    _watcher_started = True

    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
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
        test_file = skill_dir / "test-cases.json"
        meta = load_meta(skill_dir)

        broadcast_notification({
            "type": "file_changed",
            "skill_id": skill_id,
            "message": f"检测到 {skill_id}/SKILL.md 已修改",
            "has_tests": test_file.exists(),
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

    observer = Observer()
    observer.schedule(SkillFileHandler(), str(skills_path), recursive=True)
    observer.daemon = True
    observer.start()
    print(f"  👁  Watching {skills_path} for changes")

# ── Config ──────────────────────────────────────────────────
def get_skills_path() -> Path:
    env = os.environ.get("SKILLS_PATH")
    if env: return Path(env)
    local = Path(".claude") / "skills"
    if local.exists(): return local
    return Path.home() / ".claude" / "skills"

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

def check_health(skill_dir: Path) -> dict:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return {"score": 0, "grade": "F",
                "issues": [{"severity": "error", "message": "SKILL.md 不存在", "dimension": "结构"}]}
    try:
        content = skill_md.read_text(encoding='utf-8')
    except Exception as e:
        return {"score": 0, "grade": "F",
                "issues": [{"severity": "error", "message": f"无法读取: {e}", "dimension": "结构"}]}

    issues, deductions = [], 0
    fm = parse_frontmatter(content)
    if not fm.get('name'):
        issues.append({"severity": "error", "message": "frontmatter 缺少 name", "dimension": "结构"})
        deductions += 15
    desc = fm.get('description', '')
    if not desc:
        issues.append({"severity": "error", "message": "frontmatter 缺少 description", "dimension": "触发"})
        deductions += 20
    elif len(desc) < 50:
        issues.append({"severity": "warning", "message": f"description 过短（{len(desc)}字）", "dimension": "触发"})
        deductions += 10
    if desc and not re.search(r'[\u4e00-\u9fff]', desc):
        issues.append({"severity": "warning", "message": "description 缺少中文触发词", "dimension": "触发"})
        deductions += 8
    if not (skill_dir / "README.md").exists():
        issues.append({"severity": "info", "message": "缺少 README.md", "dimension": "文档"})
        deductions += 5
    if not re.search(r'(Phase|Step|步骤|阶段)\s*\d', content, re.I) and len(content) > 500:
        issues.append({"severity": "info", "message": "未发现工作流结构", "dimension": "工作流"})
        deductions += 5
    if not re.search(r'(fallback|错误|异常|失败|error|fail)', content, re.I):
        issues.append({"severity": "warning", "message": "缺少异常处理路径", "dimension": "鲁棒性"})
        deductions += 8
    if len(content) < 200:
        issues.append({"severity": "warning", "message": f"内容过短（{len(content)}字节）", "dimension": "完整性"})
        deductions += 10
    for ref in re.findall(r'`([^`]+\.(?:py|sh|json|yaml|yml))`', content):
        if not ref.startswith(('/', '~')) and not (skill_dir / ref).exists():
            issues.append({"severity": "error", "message": f"引用文件不存在: {ref}", "dimension": "依赖"})
            deductions += 10

    score = max(0, 100 - deductions)
    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D"
    return {"score": score, "grade": grade, "issues": issues}

def load_meta(skill_dir: Path) -> dict:
    f = skill_dir / ".skill-meta.json"
    if f.exists():
        try: return json.loads(f.read_text())
        except: pass
    return {}

def save_meta(skill_dir: Path, meta: dict):
    (skill_dir / ".skill-meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2))

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
                "has_tests": (d / "test-cases.json").exists(),
            })
        except Exception as e:
            skills.append({"id": d.name, "name": d.name, "error": str(e),
                           "type": "unknown", "health_score": 0,
                           "health_grade": "F", "issue_count": 1, "has_tests": False})
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
    import anthropic as ac
    client = ac.Anthropic()
    system = f"你是一个 AI 助手。以下是你需要遵循的操作指南：\n\n{skill_content}\n\n严格按照上述指南执行任务。"
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=2000,
            system=system,
            messages=[{"role": "user", "content": case["prompt"]}]
        )
        output = resp.content[0].text
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
def save_version(skill_dir: Path, label: str = "") -> str:
    vdir = skill_dir / ".versions"
    vdir.mkdir(exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    vid = f"{ts}-{label}" if label else ts
    shutil.copy2(skill_dir / "SKILL.md", vdir / f"{vid}.md")
    return vid

def list_versions(skill_dir: Path) -> list:
    vdir = skill_dir / ".versions"
    if not vdir.exists(): return []
    return [
        {"id": f.stem, "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(), "size": f.stat().st_size}
        for f in sorted(vdir.glob("*.md"), reverse=True)
    ]

def restore_version(skill_dir: Path, version_id: str) -> bool:
    src = skill_dir / ".versions" / f"{version_id}.md"
    if not src.exists(): return False
    shutil.copy2(src, skill_dir / "SKILL.md")
    return True

def append_evolution_log(skill_dir: Path, entry: dict):
    with open(skill_dir / "evolution-log.jsonl", 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')

# ── Evolution engine ─────────────────────────────────────────
def propose_improvement(skill_content: str, test_results: list, round_num: int) -> str:
    import anthropic as ac
    client = ac.Anthropic()

    failed = [r for r in test_results if r.get("score", 1) < 1.0]
    failed_summary = ""
    for r in failed:
        failed_summary += f"\n测试「{r.get('name', r['case_id'])}」得分 {r['score']:.0%}：\n"
        for d in r.get("details", []):
            if not d["passed"]:
                failed_summary += f"  - 失败: {d['reason']}\n"

    resp = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=4000,
        messages=[{"role": "user", "content": f"""你是一个 AI Skill 优化专家。请对以下 SKILL.md 提出一个具体改进。

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
{skill_content}"""}]
    )
    proposed = resp.content[0].text.strip()
    proposed = re.sub(r'^```(?:markdown|md)?\n?', '', proposed)
    proposed = re.sub(r'\n?```$', '', proposed)
    return proposed.strip()

def evolution_stream(skill_dir: Path, max_rounds: int) -> Generator:
    def event(data: dict) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    skill_md = skill_dir / "SKILL.md"
    test_cases_file = skill_dir / "test-cases.json"

    if not test_cases_file.exists():
        yield event({"type": "error", "message": "未找到 test-cases.json，请先添加测试用例"})
        return
    try:
        test_cases = json.loads(test_cases_file.read_text())["cases"]
    except Exception as e:
        yield event({"type": "error", "message": f"测试用例格式错误: {e}"}); return
    if not test_cases:
        yield event({"type": "error", "message": "测试用例为空"}); return

    yield event({"type": "start", "message": f"开始进化｜{len(test_cases)} 个测试用例｜最多 {max_rounds} 轮"})

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
    save_version(skill_dir, "baseline")
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
            "decision": "keep" if improved else "revert",
            "delta": round(new_score - best_score, 4)
        })

        if improved:
            save_version(skill_dir, f"r{round_num}-keep")
            skill_md.write_text(proposed, encoding='utf-8')
            best_score = new_score
            current_content = proposed
            current_results = new_results
            no_improve = 0
            yield event({"type": "round_done", "round": round_num, "decision": "keep",
                         "old_score": round(best_score - (new_score - best_score), 4),
                         "new_score": round(new_score, 4),
                         "message": f"✓ 保留 → {new_score:.1%}"})
        else:
            no_improve += 1
            save_version(skill_dir, f"r{round_num}-revert")
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
    return jsonify({"skills_path": str(p), "exists": p.exists()})

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
    return jsonify({
        "id": skill_id, "name": fm.get('name', skill_id),
        "description": fm.get('description', ''), "content": content,
        "health": health, "type": meta.get('type', 'unknown'),
        "modified": datetime.fromtimestamp(skill_md.stat().st_mtime).isoformat(),
    })

@app.route('/api/skills/<skill_id>/content', methods=['PUT'])
def update_content(skill_id):
    skill_md = get_skills_path() / skill_id / "SKILL.md"
    if not skill_md.exists(): return jsonify({"error": "Not found"}), 404
    skill_md.write_text(request.get_json()['content'], encoding='utf-8')
    return jsonify({"success": True})

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
        import anthropic as ac
        client = ac.Anthropic()
        resp = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=1000,
            messages=[{"role": "user", "content": f"""分析这个 SKILL.md，用 JSON 格式回复：
{{"skill_type":"verifiable|anchor|judgment","type_reason":"分类理由",
"top_issues":["问题1","问题2","问题3"],"top_suggestions":["建议1","建议2","建议3"],
"summary":"总体评价两句话"}}
只返回 JSON。
SKILL.md:
{content[:3000]}"""}]
        )
        text = re.sub(r'```(?:json)?\n?', '', resp.content[0].text).strip()
        return jsonify(json.loads(text))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Evolution
@app.route('/api/skills/<skill_id>/evolve/tests', methods=['GET'])
def get_tests(skill_id):
    f = get_skills_path() / skill_id / "test-cases.json"
    if not f.exists(): return jsonify({"cases": []})
    try: return jsonify(json.loads(f.read_text()))
    except: return jsonify({"cases": []})

@app.route('/api/skills/<skill_id>/evolve/tests', methods=['PUT'])
def save_tests(skill_id):
    skill_dir = get_skills_path() / skill_id
    if not skill_dir.exists(): return jsonify({"error": "Not found"}), 404
    (skill_dir / "test-cases.json").write_text(
        json.dumps(request.get_json(), ensure_ascii=False, indent=2))
    return jsonify({"success": True})

@app.route('/api/skills/<skill_id>/evolve/generate-tests', methods=['POST'])
def generate_tests(skill_id):
    skill_dir = get_skills_path() / skill_id
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists(): return jsonify({"error": "Not found"}), 404
    content = skill_md.read_text(encoding='utf-8')
    try:
        import anthropic as ac
        client = ac.Anthropic()
        resp = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=2000,
            messages=[{"role": "user", "content": f"""根据这个 SKILL.md，生成 2-3 个测试用例。

可用 validator 类型：
- contains: {{"type":"contains","value":"..."}}
- not_contains: {{"type":"not_contains","value":"..."}}
- min_length: {{"type":"min_length","value":100}}
- json_valid: {{"type":"json_valid"}}
- regex: {{"type":"regex","pattern":"..."}}

返回 JSON：{{"cases":[{{"id":"tc1","name":"测试名","prompt":"用户输入","validators":[...]}}]}}
只返回 JSON。

SKILL.md:
{content[:2500]}"""}]
        )
        text = re.sub(r'```(?:json)?\n?', '', resp.content[0].text).strip()
        cases = json.loads(text)
        (skill_dir / "test-cases.json").write_text(
            json.dumps(cases, ensure_ascii=False, indent=2))
        return jsonify(cases)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/skills/<skill_id>/evolve/run-tests', methods=['POST'])
def run_tests(skill_id):
    skill_dir = get_skills_path() / skill_id
    skill_md = skill_dir / "SKILL.md"
    test_cases_file = skill_dir / "test-cases.json"
    if not skill_md.exists(): return jsonify({"error": "Not found"}), 404
    if not test_cases_file.exists(): return jsonify({"error": "No test cases"}), 400
    content = skill_md.read_text(encoding='utf-8')
    cases = json.loads(test_cases_file.read_text())["cases"]
    results = [run_test_case(content, tc) for tc in cases]
    return jsonify({"results": results, "overall_score": compute_skill_score(results)})

@app.route('/api/skills/<skill_id>/evolve/start')
def start_evolution(skill_id):
    skill_dir = get_skills_path() / skill_id
    if not skill_dir.exists(): return jsonify({"error": "Not found"}), 404
    max_rounds = int(request.args.get('rounds', 5))

    def generate():
        try:
            for event in evolution_stream(skill_dir, max_rounds):
                yield event
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','message':str(e)})}\n\n"

    return Response(stream_with_context(generate()),
                    mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

@app.route('/api/skills/<skill_id>/evolve/history')
def get_history(skill_id):
    skill_dir = get_skills_path() / skill_id
    log_file = skill_dir / "evolution-log.jsonl"
    history = []
    if log_file.exists():
        for line in log_file.read_text().splitlines():
            try: history.append(json.loads(line))
            except: pass
    return jsonify({"history": history, "versions": list_versions(skill_dir)})

@app.route('/api/skills/<skill_id>/evolve/restore/<version_id>', methods=['POST'])
def restore(skill_id, version_id):
    skill_dir = get_skills_path() / skill_id
    ok = restore_version(skill_dir, version_id)
    return jsonify({"success": True} if ok else {"error": "Version not found"}), (200 if ok else 404)

# ── Baseline ─────────────────────────────────────────────────
@app.route('/api/skills/<skill_id>/evolve/set-baseline', methods=['POST'])
def set_baseline(skill_id):
    """Run tests and store the result as the baseline score for change detection."""
    skill_dir = get_skills_path() / skill_id
    skill_md = skill_dir / "SKILL.md"
    test_file = skill_dir / "test-cases.json"
    if not skill_md.exists(): return jsonify({"error": "Not found"}), 404
    if not test_file.exists(): return jsonify({"error": "No test cases"}), 400

    content = skill_md.read_text(encoding='utf-8')
    cases = json.loads(test_file.read_text())["cases"]
    results = [run_test_case(content, tc) for tc in cases]
    score = compute_skill_score(results)

    meta = load_meta(skill_dir)
    meta["last_score"] = round(score, 4)
    meta["last_tested"] = datetime.now().isoformat()
    save_meta(skill_dir, meta)

    return jsonify({"score": score, "results": results})

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
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 7890
    print(f"\n  Skills Manager  →  http://localhost:{port}\n")
    start_watcher()
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

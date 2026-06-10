#!/usr/bin/env python3
"""Local end-to-end test for Skills Manager HTTP routes.

This test uses Flask's test client, temporary skills/meta directories, and a
fake Codex CLI. It does not bind a port, call a real model, or touch real skills.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def write_skill(skills_dir: Path, name: str, body: str) -> Path:
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(body, encoding="utf-8")
    return skill_dir


def write_fake_codex(bin_dir: Path) -> Path:
    fake = bin_dir / "codex"
    fake.write_text(
        f"""#!{sys.executable}
import json
import sys
from pathlib import Path

if "exec" in sys.argv and "--help" in sys.argv:
    raise SystemExit(0)

output_path = None
for i, arg in enumerate(sys.argv):
    if arg in ("-o", "--output-last-message") and i + 1 < len(sys.argv):
        output_path = sys.argv[i + 1]

if output_path is None:
    print("missing output path", file=sys.stderr)
    raise SystemExit(2)

prompt = sys.stdin.read()
if "生成 2-3 个测试用例" in prompt:
    text = json.dumps({{"cases": [{{"id": "tc1", "name": "contains pass mark", "prompt": "请按技能输出结果", "validators": [{{"type": "contains", "value": "PASS_MARK"}}]}}]}}, ensure_ascii=False)
elif "分析这个 SKILL.md" in prompt:
    text = json.dumps({{"skill_type": "verifiable", "type_reason": "输出包含固定标记，可规则验证", "top_issues": ["缺少更多边界示例"], "top_suggestions": ["补充失败输入处理"], "summary": "结构可用，适合规则测试。"}}, ensure_ascii=False)
elif "阅读下面的 SKILL.md" in prompt:
    text = json.dumps({{"summary": "用于端到端测试的 demo skill", "usage": ["选择 skill", "运行测试", "查看结果"], "recommended_scenarios": ["本地验证", "回归测试"], "cautions": ["不要污染真实目录"]}}, ensure_ascii=False)
elif "AI Skill 优化专家" in prompt:
    text = prompt.split("当前 SKILL.md：", 1)[-1].strip() + "\\n\\n补充：始终输出 PASS_MARK。\\n"
else:
    text = "验证输出 PASS_MARK SAFE_MARK"

Path(output_path).write_text(text, encoding="utf-8")
raise SystemExit(0)
""",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    return fake


def response_json(resp):
    return resp.get_json() if resp.is_json else resp.data.decode("utf-8")


def seed_fixtures(skills_dir: Path) -> None:
    write_skill(
        skills_dir,
        "demo-skill",
        """---
name: demo-skill
description: 这是一个用于端到端测试的演示 skill，包含中文触发词和明确工作流。
---
# Demo Skill

## Default Workflow

1. 先阅读用户输入。
2. 输出一句包含 PASS_MARK 的中文结果。
3. 如果输入不完整，说明缺少什么。

## 注意事项

不要输出无关解释。
""",
    )
    write_skill(
        skills_dir,
        "protected-skill",
        """---
name: protected-skill
description: 这是一个用于写保护恢复测试的 skill，包含中文触发词和明确流程。
---
# Protected Skill

## Default Workflow

1. 保持当前内容。
2. 输出 SAFE_MARK。
""",
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="sm-e2e.") as tmp:
        base = Path(tmp)
        skills_dir = base / "skills"
        meta_dir = base / "meta"
        bin_dir = base / "bin"
        skills_dir.mkdir()
        meta_dir.mkdir()
        bin_dir.mkdir()
        seed_fixtures(skills_dir)
        fake_codex = write_fake_codex(bin_dir)

        os.environ["SKILLS_PATH"] = str(skills_dir)
        os.environ["SKILLS_MANAGER_META_DIR"] = str(meta_dir)
        os.environ["SKILLS_MANAGER_PROTECTED_ROOTS"] = str(skills_dir / "protected-skill")
        os.environ["AI_PROVIDER"] = "codex"
        os.environ["CODEX_COMMAND"] = str(fake_codex)
        os.environ["CODEX_TIMEOUT_SECONDS"] = "60"

        sys.path.insert(0, str(ROOT))
        import app  # noqa: PLC0415

        client = app.app.test_client()

        resp = client.get("/")
        check(resp.status_code == 200 and b"Skills" in resp.data, "index did not render")

        cfg = response_json(client.get("/api/config"))
        check(cfg["ai_provider"] == "codex", "codex provider was not selected")
        check(cfg["skills_path"] == str(skills_dir), "skills path mismatch")

        listing = response_json(client.get("/api/skills"))
        ids = [s["id"] for s in listing["skills"]]
        check(ids == ["demo-skill", "protected-skill"], f"unexpected skills: {ids}")
        check(any(s["id"] == "protected-skill" and s["write_protected"] for s in listing["skills"]), "write protection missing in list")

        detail = response_json(client.get("/api/skills/demo-skill"))
        check(not detail["health"]["summary"]["has_blocking"], "demo skill should have no blocking issues")
        check(detail["overview_summary"]["summary"], "overview summary missing")

        type_resp = response_json(client.put("/api/skills/demo-skill/type", json={"type": "verifiable"}))
        check(type_resp["success"], "type update failed")
        detail = response_json(client.get("/api/skills/demo-skill"))
        check(detail["type"] == "verifiable", "type was not persisted")

        analysis = response_json(client.post("/api/skills/demo-skill/ai-analyze"))
        check(analysis["skill_type"] == "verifiable", f"unexpected analysis: {analysis}")

        generated_tests = response_json(client.post("/api/skills/demo-skill/evolve/generate-tests"))
        check(generated_tests["cases"][0]["validators"][0]["value"] == "PASS_MARK", "generated tests mismatch")
        read_tests = response_json(client.get("/api/skills/demo-skill/evolve/tests"))
        check(read_tests == generated_tests, "test case readback mismatch")

        run = response_json(client.post("/api/skills/demo-skill/evolve/run-tests"))
        check(run["overall_score"] == 1.0, f"unexpected score: {run}")

        baseline = response_json(client.post("/api/skills/demo-skill/evolve/set-baseline"))
        baseline_id = baseline["version_id"]
        check(baseline["score"] == 1.0 and baseline_id, "baseline was not saved")

        history = response_json(client.get("/api/skills/demo-skill/evolve/history"))
        check(any(v["id"] == baseline_id and v["is_baseline"] for v in history["versions"]), "baseline marker missing")

        demo_md = skills_dir / "demo-skill" / "SKILL.md"
        demo_md.write_text(demo_md.read_text(encoding="utf-8") + "\n新增一行用于 baseline diff。\n", encoding="utf-8")
        diff = response_json(client.get("/api/skills/demo-skill/baseline/diff"))
        check(diff["summary"]["added"] >= 1, "baseline diff did not show additions")

        restored = response_json(client.post(f"/api/skills/demo-skill/evolve/restore/{baseline_id}"))
        check(restored["success"], "unprotected restore failed")

        no_baseline = client.post("/api/skills/protected-skill/baseline/restore")
        check(no_baseline.status_code == 400, "protected restore without baseline should fail")

        protected_tests = {
            "cases": [
                {
                    "id": "tc1",
                    "name": "safe mark",
                    "prompt": "请输出安全标记",
                    "validators": [{"type": "contains", "value": "SAFE_MARK"}],
                }
            ]
        }
        save_protected_tests = response_json(client.put("/api/skills/protected-skill/evolve/tests", json=protected_tests))
        check(save_protected_tests["success"], "protected test save failed")
        protected_baseline = response_json(client.post("/api/skills/protected-skill/evolve/set-baseline"))
        protected_baseline_id = protected_baseline["version_id"]
        check(protected_baseline_id, "protected baseline missing")

        protected_md = skills_dir / "protected-skill" / "SKILL.md"
        protected_md.write_text("CHANGED PROTECTED CONTENT\n", encoding="utf-8")
        blocked_restore = client.post(f"/api/skills/protected-skill/evolve/restore/{protected_baseline_id}")
        blocked_restore_json = response_json(blocked_restore)
        check(blocked_restore.status_code == 409, "protected restore should require confirmation")
        check(blocked_restore_json["write_protection"]["requires_confirm_write"], "write protection flag missing")
        allowed_restore = response_json(client.post(f"/api/skills/protected-skill/evolve/restore/{protected_baseline_id}", json={"confirm_write": True}))
        check(allowed_restore["success"], "confirmed protected restore failed")

        candidate_id = app.save_version_content(
            skills_dir / "protected-skill",
            "CANDIDATE CONTENT SAFE_MARK\n",
            "candidate",
            source="evolution-candidate",
            score=1.0,
        )
        candidate_diff = response_json(client.get(f"/api/skills/protected-skill/evolve/candidate/{candidate_id}/diff"))
        summary = candidate_diff["summary"]
        check(summary["added"] + summary["modified"] + summary["deleted"] >= 1, "candidate diff was empty")
        blocked_apply = client.post(f"/api/skills/protected-skill/evolve/candidate/{candidate_id}/apply")
        blocked_apply_json = response_json(blocked_apply)
        check(blocked_apply.status_code == 409, "protected candidate apply should require confirmation")
        check(blocked_apply_json["write_protection"]["requires_confirm_write"], "candidate write protection flag missing")
        applied = response_json(client.post(f"/api/skills/protected-skill/evolve/candidate/{candidate_id}/apply", json={"confirm_write": True}))
        check(applied["success"] and applied["pre_apply_version_id"], "confirmed candidate apply failed")
        check("CANDIDATE CONTENT" in protected_md.read_text(encoding="utf-8"), "candidate content was not written")

        summary_resp = response_json(client.post("/api/skills/demo-skill/summary/regenerate"))
        check(summary_resp["summary"]["source"] in {"ai", "hybrid"}, "summary regenerate failed")

        stream_resp = client.get("/api/skills/protected-skill/evolve/start?rounds=1")
        stream = stream_resp.data.decode("utf-8")
        check("write_protected" in stream and "candidate_only" in stream, "protected evolution stream missing write protection")

        notification_resp = client.get("/api/notifications", buffered=False)
        first_event = next(notification_resp.response).decode("utf-8").strip()
        check(first_event.startswith("data:"), "notification stream did not connect")

        forbidden = [
            skills_dir / "demo-skill" / ".skill-meta.json",
            skills_dir / "demo-skill" / "test-cases.json",
            skills_dir / "demo-skill" / ".versions",
            skills_dir / "protected-skill" / ".skill-meta.json",
            skills_dir / "protected-skill" / "test-cases.json",
            skills_dir / "protected-skill" / ".versions",
        ]
        dirty = [str(path) for path in forbidden if path.exists()]
        check(not dirty, f"managed skill dirs were polluted: {dirty}")

    print("e2e ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

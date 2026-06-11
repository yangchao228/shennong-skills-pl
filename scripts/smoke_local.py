#!/usr/bin/env python3
"""Local smoke test for Skills Manager core workflows."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def write_demo_skill(skills_dir: Path) -> Path:
    skill_dir = skills_dir / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: demo
description: 这是一个用于 smoke test 的 demo skill，描述足够长并包含中文触发词。
---
# Demo

## Default Workflow

Step 1. Old content.

If anything fails, explain the error.
""",
        encoding="utf-8",
    )
    return skill_dir

def write_fake_codex(bin_dir: Path) -> Path:
    fake = bin_dir / "codex"
    fake.write_text(
        f"""#!{sys.executable}
import sys
from pathlib import Path

if sys.argv[1:3] == ["exec", "--help"]:
    raise SystemExit(0)

output_path = None
for i, arg in enumerate(sys.argv):
    if arg in ("-o", "--output-last-message") and i + 1 < len(sys.argv):
        output_path = sys.argv[i + 1]

if output_path is None:
    print("missing output path", file=sys.stderr)
    raise SystemExit(2)

_ = sys.stdin.read()
Path(output_path).write_text('{{"summary":"fake codex ok","usage":[],"recommended_scenarios":[],"cautions":[]}}', encoding="utf-8")
raise SystemExit(0)
""",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    return fake


def assert_skill_dir_clean(skill_dir: Path) -> None:
    forbidden = [
        skill_dir / ".skill-meta.json",
        skill_dir / "test-cases.json",
        skill_dir / ".versions",
        skill_dir / "evolution-log.jsonl",
    ]
    dirty = [str(path) for path in forbidden if path.exists()]
    check(not dirty, f"managed skill dir was polluted: {dirty}")


def run_node_check() -> None:
    node = shutil.which("node")
    if not node:
        print("skip node --check: node not found")
        return
    html = ROOT / "static" / "index.html"
    script_lines: list[str] = []
    inside = False
    for line in html.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "<script>":
            inside = True
            continue
        if stripped == "</script>":
            inside = False
            continue
        if inside:
            script_lines.append(line)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tmp:
        tmp.write("\n".join(script_lines))
        tmp_path = tmp.name
    try:
        subprocess.run([node, "--check", tmp_path], check=True)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="sm-skills.") as skills_tmp, tempfile.TemporaryDirectory(prefix="sm-meta.") as meta_tmp, tempfile.TemporaryDirectory(prefix="sm-bin.") as bin_tmp:
        skills_dir = Path(skills_tmp)
        meta_dir = Path(meta_tmp)
        fake_codex = write_fake_codex(Path(bin_tmp))
        skill_dir = write_demo_skill(skills_dir)

        os.environ["SKILLS_PATH"] = str(skills_dir)
        os.environ["SKILLS_MANAGER_META_DIR"] = str(meta_dir)
        os.environ["SKILLS_MANAGER_PROTECTED_ROOTS"] = str(skills_dir)
        os.environ["AI_PROVIDER"] = "codex"
        os.environ["CODEX_COMMAND"] = str(fake_codex)
        os.environ["CODEX_MODEL"] = "fake-model"

        sys.path.insert(0, str(ROOT))
        import app  # noqa: PLC0415

        client = app.app.test_client()
        check(app.resolve_ai_provider() == "codex", "codex provider did not resolve")
        codex_json = app.ollama_generate_json("return json")
        check(codex_json["summary"] == "fake codex ok", "codex json generation failed")

        cfg = client.get("/api/config").get_json()
        check(cfg["skills_path"] == str(skills_dir), "config skills_path mismatch")
        check(cfg["meta_path"] == str(meta_dir), "config meta_path mismatch")

        listing = client.get("/api/skills").get_json()
        check(listing["total"] == 1, "expected one demo skill")
        check(listing["skills"][0]["write_protected"] is True, "demo skill should be write protected")

        detail = client.get("/api/skills/demo").get_json()
        check(detail["health"]["score"] >= 75, "demo health score unexpectedly low")
        check(detail["write_protection"]["requires_confirm_write"] is True, "detail write protection missing")

        type_resp = client.put("/api/skills/demo/type", json={"type": "verifiable"}).get_json()
        check(type_resp["success"] is True, "type update failed")
        detail = client.get("/api/skills/demo").get_json()
        check(detail["type"] == "verifiable", "type not stored in external meta")

        fb_initial = client.get("/api/skills/demo/feedback/config").get_json()
        check(fb_initial["enabled"] is False, "feedback should start disabled")
        fb_config = client.post("/api/skills/demo/feedback/config", json={"enabled": True}).get_json()
        check(fb_config["enabled"] is True, "feedback config was not enabled")
        check(fb_config["token"], "feedback token missing")
        check(fb_config["fallback_file"].endswith("feedback.jsonl"), "feedback fallback file missing")
        check(app.FEEDBACK_MARKER_START in fb_config["snippet"], "feedback snippet marker missing")
        check("Fallback file:" in fb_config["snippet"], "feedback fallback path missing from snippet")
        check("Fallback command" in fb_config["snippet"], "feedback fallback command missing from snippet")
        check('+ "\\\\n")' in fb_config["snippet"], "feedback fallback newline escaping is broken")
        check(fb_config["summary"]["added"] >= 1, "feedback install diff missing")
        blocked_feedback_install = client.post("/api/skills/demo/feedback/install")
        check(blocked_feedback_install.status_code == 409, "protected feedback install should require confirmation")
        check(app.FEEDBACK_MARKER_START not in (skill_dir / "SKILL.md").read_text(encoding="utf-8"), "blocked feedback install changed SKILL.md")
        installed_feedback = client.post("/api/skills/demo/feedback/install", json={"confirm_write": True}).get_json()
        check(installed_feedback["success"] is True, "confirmed feedback install failed")
        skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        check(skill_text.count(app.FEEDBACK_MARKER_START) == 1, "feedback snippet should be installed once")
        installed_again = client.post("/api/skills/demo/feedback/install", json={"confirm_write": True}).get_json()
        check(installed_again["success"] is True, "repeat feedback install failed")
        skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        check(skill_text.count(app.FEEDBACK_MARKER_START) == 1, "repeat feedback install duplicated snippet")
        bad_feedback = client.post(
            "/api/feedback/runs",
            headers={"X-Skills-Manager-Feedback-Token": "wrong"},
            json={"skill_id": "demo", "install_id": fb_config["install_id"], "rating": "neutral"},
        )
        check(bad_feedback.status_code == 403, "invalid feedback token should be rejected")
        feedback_post = client.post(
            "/api/feedback/runs",
            headers={"X-Skills-Manager-Feedback-Token": fb_config["token"]},
            json={
                "skill_id": "demo",
                "install_id": fb_config["install_id"],
                "run_id": "run-1",
                "agent": "codex",
                "rating": "neutral",
                "task_summary": "smoke feedback",
                "what_failed": "final evidence was unclear",
                "suggested_fix": "add completion evidence",
                "evidence": ["scripts/smoke_local.py"],
            },
        ).get_json()
        check(feedback_post["success"] is True, "feedback post failed")
        fallback_event = {
            "id": "fallback-smoke-1",
            "skill_id": "demo",
            "install_id": fb_config["install_id"],
            "run_id": "fallback-run-1",
            "agent": "codex",
            "rating": "negative",
            "task_summary": "fallback feedback",
            "what_worked": "fallback jsonl was writable",
            "what_failed": "endpoint was unavailable",
            "suggested_fix": "keep local jsonl fallback",
            "evidence": ["fallback file"],
            "created_at": "2999-01-01T00:00:00",
        }
        with open(fb_config["fallback_file"], "a", encoding="utf-8") as f:
            f.write(json.dumps(fallback_event, ensure_ascii=False) + "\n")
        feedback_list = client.get("/api/skills/demo/feedback").get_json()
        check(len(feedback_list["feedback"]) == 2, "feedback readback missing")
        check(feedback_list["feedback"][0]["run_id"] == "fallback-run-1", "fallback feedback readback mismatch")
        check(feedback_list["feedback"][1]["rating"] == "neutral", "feedback rating mismatch")
        assert_skill_dir_clean(skill_dir)

        test_cases = {"cases": [{"id": "tc1", "name": "basic", "prompt": "x", "validators": []}]}
        tests_resp = client.put("/api/skills/demo/evolve/tests", json=test_cases).get_json()
        check(tests_resp["success"] is True, "test case save failed")
        check(client.get("/api/skills/demo/evolve/tests").get_json() == test_cases, "test case readback mismatch")
        assert_skill_dir_clean(skill_dir)

        version_id = app.save_version_content(skill_dir, "NEW VERSION", "manual-new", source="manual")
        blocked = client.post(f"/api/skills/demo/evolve/restore/{version_id}")
        check(blocked.status_code == 409, "protected restore without confirmation should be blocked")
        check("Old content" in (skill_dir / "SKILL.md").read_text(encoding="utf-8"), "blocked restore changed SKILL.md")
        allowed = client.post(f"/api/skills/demo/evolve/restore/{version_id}", json={"confirm_write": True})
        check(allowed.status_code == 200, "confirmed restore failed")
        check((skill_dir / "SKILL.md").read_text(encoding="utf-8") == "NEW VERSION", "confirmed restore did not apply")

        # Reset content for candidate flow.
        (skill_dir / "SKILL.md").write_text("CURRENT VERSION\n", encoding="utf-8")
        candidate_id = app.save_version_content(
            skill_dir,
            "CURRENT VERSION\nCandidate content.\n",
            "r1-candidate",
            source="evolution-candidate",
            score=1.0,
            note="candidate",
        )
        manual_id = app.save_version_content(skill_dir, "MANUAL\n", "manual", source="manual")

        diff = client.get(f"/api/skills/demo/evolve/candidate/{candidate_id}/diff")
        check(diff.status_code == 200, "candidate diff failed")
        check(diff.get_json()["summary"]["added"] >= 1, "candidate diff did not show additions")
        not_candidate = client.post(f"/api/skills/demo/evolve/candidate/{manual_id}/apply", json={"confirm_write": True})
        check(not_candidate.status_code == 400, "manual version should not apply as candidate")
        blocked_apply = client.post(f"/api/skills/demo/evolve/candidate/{candidate_id}/apply")
        check(blocked_apply.status_code == 409, "protected candidate apply without confirmation should be blocked")
        applied = client.post(f"/api/skills/demo/evolve/candidate/{candidate_id}/apply", json={"confirm_write": True})
        check(applied.status_code == 200, "confirmed candidate apply failed")
        check("Candidate content" in (skill_dir / "SKILL.md").read_text(encoding="utf-8"), "candidate was not applied")
        versions = app.list_versions(skill_dir)
        check(any(v["source"] == "pre-apply-candidate" for v in versions), "pre-apply-candidate snapshot missing")

        # Deterministic evolution check: protected skills should save candidates, not write SKILL.md.
        (skill_dir / "SKILL.md").write_text("EVOLUTION BASE\n", encoding="utf-8")

        def fake_run_test_case(content: str, case: dict) -> dict:
            score = 1.0 if "Better content" in content else 0.0
            return {"case_id": case["id"], "name": case["name"], "passed": int(score), "total": 1, "score": score, "details": []}

        def fake_propose(content: str, results: list, round_num: int) -> str:
            return content + "Better content.\n"

        app.run_test_case = fake_run_test_case
        app.propose_improvement = fake_propose
        events = "".join(app.evolution_stream(skill_dir, 1))
        check("write_protected" in events, "evolution did not report write protection")
        check("candidate" in events, "evolution did not save candidate")
        check("Better content" not in (skill_dir / "SKILL.md").read_text(encoding="utf-8"), "protected evolution wrote SKILL.md")
        versions = app.list_versions(skill_dir)
        check(any(v["source"] == "evolution-candidate" for v in versions), "evolution candidate version missing")

        assert_skill_dir_clean(skill_dir)

    run_node_check()
    print("smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

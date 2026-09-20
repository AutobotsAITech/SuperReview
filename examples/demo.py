#!/usr/bin/env python3
"""Offline synthetic walkthrough; the finding is prewritten, not model-generated."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("superreview", ROOT / "skills/superreview/scripts/superreview.py")
sr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sr)


def main():
    directory = Path(tempfile.mkdtemp(prefix="superreview-demo-"))
    repo = directory / "repo"
    repo.mkdir()
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)

    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args], env=env).decode().strip()

    git("init", "-q")
    git("config", "user.name", "demo")
    git("config", "user.email", "demo@invalid")
    source = repo / "session.py"
    source.write_text("def load_session(storage, tenant, key):\n    return storage.find(tenant=tenant, key=key)\n")
    git("add", "session.py")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")
    source.write_text("def load_session(storage, tenant, key):\n    return storage.find(key=key)\n")
    git("add", "session.py")
    git("commit", "-qm", "remove tenant scope")
    plan = sr.create_plan(repo, base, "HEAD")
    report = sr.init_report(plan)
    for unit in report["coverage"]:
        unit.update(status="reviewed", reason="Synthetic walkthrough: inspected the complete two-line change and the stated storage contract.")
    report["findings"] = [{"path": "session.py", "side": "head", "line": 2,
        "symbol": "load_session", "root_cause": "missing-tenant-scope", "severity": "P1",
        "title": "Session lookup no longer enforces the tenant boundary",
        "trigger": "A caller supplies a valid key belonging to another tenant.",
        "evidence": "The changed storage call omits tenant; the synthetic contract states storage applies only supplied filters.",
        "impact": "The lookup can return another tenant's session.",
        "refutation": "No implicit tenant filter or ownership check exists in the stated fixture contract.",
        "verification": "reasoned", "fix": "Keep the tenant constraint and test cross-tenant requests."}]
    sr.validate_report(plan, report)
    sr.write_json(directory / "plan.json", plan)
    sr.write_json(directory / "report.json", report)
    sr.write_new(directory / "review.md", sr.render(plan, report))
    assert sr.gate_result(plan, report) == 1, "The known P1 defect must fail the gate"
    print("Synthetic, prewritten review validated; P1 gate correctly rejected the change.")
    print("Report: " + str(directory / "review.md"))
    print("Temporary artifacts are retained for inspection; remove this demo directory when finished.")
    return directory


if __name__ == "__main__":
    main()

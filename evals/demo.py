#!/usr/bin/env python3
"""Create synthetic saved reviews for exercising the optional scoring integration."""
import argparse
import copy
import contextlib
import importlib.util
import io
from pathlib import Path
import shutil

import score_reviews as scoring


def create(destination):
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location("synthetic_demo", scoring.ROOT / "examples/demo.py")
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    with contextlib.redirect_stdout(io.StringIO()):
        generated = demo.main()
    try:
        plan = scoring.sr.load_json(generated / "plan.json")
        report = scoring.sr.load_json(generated / "report.json")
        scoring.sr.write_json(destination / "plan.json", plan)
        cases = []
        for name, found in (("supported", True), ("missed", False)):
            saved = copy.deepcopy(report)
            if not found:
                saved["findings"] = []
            feedback = scoring.rw.feedback(plan, saved)
            for row in feedback["decisions"]:
                row.update(decision="accepted", reason="Supported by the synthetic storage contract.")
            scoring.sr.write_json(destination / (name + ".json"), saved)
            scoring.sr.write_json(destination / (name + "-feedback.json"), feedback)
            cases.append({"id": name, "revision": "synthetic-v1", "known_defects": ["tenant-scope"],
                          "status": "complete", "plan": "plan.json", "report": name + ".json",
                          "feedback": name + "-feedback.json",
                          "matches": {d["finding"]: ["tenant-scope"] for d in feedback["decisions"]}})
        cases.append({"id": "failed-run", "revision": "synthetic-v1", "known_defects": ["tenant-scope"],
                      "status": "execution-error"})
        scoring.sr.write_json(destination / "manifest.json", {"schema_version": 1, "cases": cases})
    finally:
        shutil.rmtree(generated)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="new fixture directory")
    args = parser.parse_args()
    create(args.out)
    print("Synthetic fixtures: " + str(args.out / "manifest.json"))
    print("Expected: one pass, one missed defect, one execution error. No model was run.")

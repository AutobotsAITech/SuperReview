#!/usr/bin/env python3
"""Score saved reviews against explicit human decisions; never invoke a model."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/superreview/scripts"))
import superreview as sr
import review_workflow as rw


def artifact(root, name):
    sr.require(isinstance(name, str) and name, "artifact path must be a nonempty string")
    path = root / name
    sr.require(not Path(name).is_absolute() and root in path.resolve().parents,
               "artifacts must be inside the manifest directory")
    return sr.load_json(path)


def load_cases(manifest):
    manifest = Path(manifest).resolve()
    data = sr.load_json(manifest)
    sr.keys(data, ("schema_version", "cases"), "evaluation manifest")
    sr.require(type(data["schema_version"]) is int and data["schema_version"] == 1,
               "unsupported evaluation schema")
    sr.require(isinstance(data["cases"], list) and data["cases"], "cases must be nonempty")
    seen, records = set(), []
    for row in data["cases"]:
        sr.require(isinstance(row, dict), "case must be an object")
        status = row.get("status")
        sr.require(status in ("complete", "execution-error"), "invalid run status")
        fields = ("id", "revision", "known_defects", "status")
        if status == "complete":
            fields += ("plan", "report", "feedback", "matches")
        sr.keys(row, fields, "evaluation case")
        for key in ("id", "revision"):
            sr.string(row[key], key)
        sr.require(row["id"] not in seen, "duplicate case ID")
        seen.add(row["id"])
        known = row["known_defects"]
        sr.require(isinstance(known, list), "known_defects must be an array")
        for value in known:
            sr.string(value, "defect ID")
        sr.require(len(known) == len(set(known)), "duplicate known defect ID")
        record = {"id": row["id"], "revision": row["revision"], "known_defects": known,
                  "error": "saved execution failed" if status == "execution-error" else None}
        if status == "complete":
            plan = artifact(manifest.parent, row["plan"])
            report = artifact(manifest.parent, row["report"])
            feedback = rw.feedback(plan, report, artifact(manifest.parent, row["feedback"]))
            decisions = feedback["decisions"]
            counts = Counter(item["decision"] for item in decisions)
            matches = row["matches"]
            sr.require(isinstance(matches, dict), "matches must map findings to defect IDs")
            accepted = {item["finding"] for item in decisions if item["decision"] == "accepted"}
            sr.require(set(matches) == accepted, "matches must cover exactly the accepted findings")
            matched = set()
            for values in matches.values():
                sr.require(isinstance(values, list), "each match must be an array")
                for value in values:
                    sr.require(isinstance(value, str) and value in known, "unknown matched defect")
                sr.require(len(values) == len(set(values)), "duplicate matched defect")
                matched.update(values)
            if counts["pending"]:
                record["error"] = "human adjudication is incomplete"
            elif report["limitations"] or any(u["status"] == "not-reviewed" for u in report["coverage"]):
                record["error"] = "review coverage is incomplete"
            record["metrics"] = {
                "proposed": len(decisions), "supported": counts["accepted"],
                "rejected": counts["rejected"], "duplicates": counts["duplicate"],
                "out_of_scope": counts["out-of-scope"], "known": len(known),
                "found": len(matched),
            }
            record["evidence"] = {"plan_id": plan["plan_id"], "report_digest": sr.digest(report),
                                  "feedback_digest": sr.digest(feedback)}
        records.append(record)
    return records


def summarize(records):
    completed = [r for r in records if not r["error"]]
    counts = Counter()
    for record in completed:
        counts.update(record["metrics"])
    precision = counts["supported"] / counts["proposed"] if counts["proposed"] else None
    recall = counts["found"] / counts["known"] if counts["known"] else None
    return {"cases": len(records), "scored_cases": len(completed),
            "unscored_cases": len(records) - len(completed),
            "counts": dict(counts), "precision": precision, "known_defect_recall": recall,
            "scope": "Fully reviewed and adjudicated cases only; null means no denominator."}


def evaluate(records, output):
    from multivon_eval import EvalCase, EvalSuite, declare_dependencies, declare_target
    from multivon_eval.evaluators.base import Evaluator

    class ReviewOutcome(Evaluator):
        name = "review_outcome"

        def evaluate(self, case, text):
            metrics = json.loads(text)
            passed = (metrics["supported"] == metrics["proposed"]
                      and metrics["found"] == metrics["known"])
            return self._result(float(passed),
                                "All proposed findings supported and all known defects found."
                                if passed else "Unsupported, duplicate, out-of-scope, or missed findings.",
                                **metrics)

    suite = EvalSuite("superreview-saved-reviews", purpose="regression")
    suite.add_cases([EvalCase(input=r["id"], case_id=r["id"], revision=r["revision"],
                             metadata={"known_defects": r["known_defects"]}) for r in records])
    suite.add_evaluators(declare_dependencies(
        ReviewOutcome(threshold=1.0), version="superreview-adjudication/v1",
        dependencies={}, files={"scorer": Path(__file__)}))
    lookup = {r["id"]: r for r in records}

    def saved_review(case_id):
        record = lookup[case_id]
        if record["error"]:
            raise RuntimeError(record["error"])
        return json.dumps(record["metrics"], sort_keys=True)

    target = declare_target(saved_review, version="superreview-saved-reviews/v1",
                            dependencies={"saved_records": sr.digest(records)},
                            files={"scorer": Path(__file__), "report_contract": Path(sr.__file__),
                                   "feedback_contract": Path(rw.__file__)})
    report = suite.run(target, workers=1, verbose=False,
                       save_json=str(output / "multivon.json"),
                       save_html=str(output / "multivon.html"))
    summary = summarize(records)
    summary["passed_cases"] = report.passed
    summary["note"] = "Saved-output scoring; Multivon latency is grading time, not agent review time."
    sr.write_json(output / "summary.json", summary)
    return 2 if summary["unscored_cases"] or report.errors else (1 if report.passed != len(records) else 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="new local output directory")
    args = parser.parse_args()
    try:
        records = load_cases(args.manifest)
        args.out.mkdir(mode=0o700, parents=True, exist_ok=False)
        result = evaluate(records, args.out)
    except ImportError:
        print("Install evals/requirements.txt with Python 3.10+ to use Multivon.", file=sys.stderr)
        return 2
    except (sr.ReviewError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print("Saved evaluation: " + str(args.out / "summary.json"))
    return result


if __name__ == "__main__":
    sys.exit(main())

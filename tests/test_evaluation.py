"""Scoring must preserve missing evidence and bind judgments to exact reports."""
import copy
import json
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
import score_reviews as scoring
import demo as eval_demo


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "fixtures"
        eval_demo.create(self.root)
        self.path = self.root / "manifest.json"
        self.manifest = scoring.sr.load_json(self.path)

    def save_manifest(self):
        self.path.write_text(json.dumps(self.manifest))

    def test_scoring_keeps_errors_out_of_quality_denominators(self):
        result = scoring.summarize(scoring.load_cases(self.path))
        self.assertEqual((result["cases"], result["scored_cases"], result["unscored_cases"]), (3, 2, 1))
        self.assertEqual(result["precision"], 1.0)
        self.assertEqual(result["known_defect_recall"], 0.5)

    def test_empty_denominators_are_unknown(self):
        result = scoring.summarize([{"error": None, "metrics": {"known": 0, "proposed": 0}}])
        self.assertIsNone(result["precision"])
        self.assertIsNone(result["known_defect_recall"])

    def test_feedback_cannot_be_reused_after_report_changes(self):
        path = self.root / "supported.json"
        report = scoring.sr.load_json(path)
        report["findings"][0]["title"] = "Changed claim"
        path.write_text(json.dumps(report))
        with self.assertRaisesRegex(scoring.sr.ReviewError, "different report"):
            scoring.load_cases(self.path)

    def test_unknown_defects_and_duplicate_cases_are_rejected(self):
        original = copy.deepcopy(self.manifest)
        finding = next(iter(self.manifest["cases"][0]["matches"]))
        self.manifest["cases"][0]["matches"][finding] = ["invented"]
        self.save_manifest()
        with self.assertRaisesRegex(scoring.sr.ReviewError, "unknown matched"):
            scoring.load_cases(self.path)
        self.manifest = original
        self.manifest["cases"].append(copy.deepcopy(self.manifest["cases"][0]))
        self.save_manifest()
        with self.assertRaisesRegex(scoring.sr.ReviewError, "duplicate case"):
            scoring.load_cases(self.path)

    def test_incomplete_adjudication_cannot_count_as_success(self):
        path = self.root / "supported-feedback.json"
        feedback = scoring.sr.load_json(path)
        feedback["decisions"][0]["decision"] = "pending"
        path.write_text(json.dumps(feedback))
        self.manifest["cases"][0]["matches"] = {}
        self.save_manifest()
        self.assertEqual(scoring.summarize(scoring.load_cases(self.path))["unscored_cases"], 2)

    def test_artifacts_cannot_escape_manifest_directory(self):
        self.manifest["cases"][0]["plan"] = "../outside.json"
        self.save_manifest()
        with self.assertRaisesRegex(scoring.sr.ReviewError, "inside"):
            scoring.load_cases(self.path)

    def test_noise_stays_in_precision_denominator(self):
        report_path = self.root / "supported.json"
        report = scoring.sr.load_json(report_path)
        extra = dict(report["findings"][0], root_cause="unsupported-variant")
        report["findings"].append(extra)
        report_path.write_text(json.dumps(report))
        plan = scoring.sr.load_json(self.root / "plan.json")
        for decision in ("rejected", "duplicate", "out-of-scope"):
            with self.subTest(decision=decision):
                feedback = scoring.rw.feedback(plan, report)
                first, second = feedback["decisions"]
                first.update(decision="accepted", reason="Synthetic supported finding.")
                second.update(decision=decision, reason="Synthetic noise control.",
                              duplicate_of=first["finding"] if decision == "duplicate" else "")
                (self.root / "supported-feedback.json").write_text(json.dumps(feedback))
                summary = scoring.summarize(scoring.load_cases(self.path))
                self.assertEqual(summary["precision"], 0.5)
                self.assertEqual(summary["counts"]["proposed"], 2)

    def test_coverage_gaps_remain_unscored(self):
        path = self.root / "missed.json"
        report = scoring.sr.load_json(path)
        report["limitations"] = ["Required caller context was unavailable."]
        path.write_text(json.dumps(report))
        plan = scoring.sr.load_json(self.root / "plan.json")
        (self.root / "missed-feedback.json").write_text(json.dumps(scoring.rw.feedback(plan, report)))
        self.assertEqual(scoring.summarize(scoring.load_cases(self.path))["unscored_cases"], 2)

    @unittest.skipUnless(importlib.util.find_spec("multivon_eval"), "optional Multivon dependency")
    def test_multivon_preserves_failed_runs_and_saves_reports(self):
        output = Path(self.tmp.name) / "results"
        output.mkdir()
        self.assertEqual(scoring.evaluate(scoring.load_cases(self.path), output), 2)
        summary = scoring.sr.load_json(output / "summary.json")
        self.assertEqual(summary["passed_cases"], 1)
        self.assertTrue((output / "multivon.html").is_file())


if __name__ == "__main__":
    unittest.main()

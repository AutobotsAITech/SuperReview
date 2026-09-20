# Score saved reviews with Multivon

The optional [multivon-eval](https://github.com/multivon-ai/multivon-eval) adapter scores local
SuperReview reports using explicit human decisions. It makes no model or judge calls and
is not required by the review skill. Python 3.10+ is required for this integration.

## Try the synthetic walkthrough

From a SuperReview checkout:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r evals/requirements.txt
python evals/demo.py --out /tmp/superreview-eval-example
python evals/score_reviews.py /tmp/superreview-eval-example/manifest.json \
  --out /tmp/superreview-eval-results
```

Use new output directories. The walkthrough deliberately includes one supported review,
one missed defect, and one failed run. The scorer exits **2**, writes local JSON and HTML,
and reports one passing case, one quality failure, and one unscored case. These prewritten
fixtures demonstrate accounting; they are not an accuracy benchmark.

## Score your own reviews

1. Save the `plan.json` and `report.json` from each review.
2. Use the helper's `feedback` command to annotate every finding. Accept a finding only after
   checking the introduced defect, reachability, and impact. Resolve pending judgments.
3. Build a manifest next to those artifacts. Give each case a stable ID and dataset revision.
   List known defect IDs, and map accepted finding fingerprints to the defects they identify.

```json
{
  "schema_version": 1,
  "cases": [
    {
      "id": "tenant-scope",
      "revision": "dataset-v1",
      "known_defects": ["missing-tenant-filter"],
      "status": "complete",
      "plan": "case-1/plan.json",
      "report": "case-1/report.json",
      "feedback": "case-1/feedback.json",
      "matches": {"FINDING_FINGERPRINT": ["missing-tenant-filter"]}
    },
    {
      "id": "interrupted-review",
      "revision": "dataset-v1",
      "known_defects": [],
      "status": "execution-error"
    }
  ]
}
```

Replace the placeholder fingerprint with the `finding` value from the feedback file.
`matches` must contain exactly the accepted findings. An empty match list is allowed for a
supported defect outside the known-defect set. Use `known_defects: []` for an adjudicated
clean control; do not infer cleanliness from a report with no findings.

Paths must stay inside the manifest directory. The scorer validates reports and their
feedback digests before scoring. Modified reports require new adjudication. Human decisions
are inputs, not independently verified truth; keep raw evidence and adjudication rationale.

## Read the results

| Output | Meaning |
| --- | --- |
| `summary.json` | Counts, precision, known-defect recall, and unscored cases |
| `multivon.json` | Per-case evaluation results and grader metadata |
| `multivon.html` | Local report for inspecting outcomes |

Precision is accepted findings divided by all proposed findings, including duplicates and
out-of-scope findings in the denominator. Known-defect recall is distinct matched defects
divided by listed known defects. Both are pooled over fully reviewed, fully adjudicated cases;
zero denominators produce `null`. These are descriptive ratios, not confidence estimates.

A case passes only when every finding is supported and every known defect is found. Execution
errors, pending judgments, and incomplete coverage are unscored and force exit 2. Quality
failures produce exit 1; all cases passing produces exit 0. The Multivon case pass rate is
not finding precision. Duplicate and out-of-scope decisions remain separate counts.

Multivon's reported latency here measures saved-output grading, not the original review.
Retain original runner latency and provider cost separately. Re-scoring saved outputs is not
an independent model trial. Reports may contain sensitive case identifiers; keep them private.

Use the [evaluation protocol](README.md) for sampling, blinded review, clean controls, and
comparative experiments. Maintainer-run scoring does not constitute independent validation.

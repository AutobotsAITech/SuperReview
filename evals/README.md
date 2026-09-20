# Evaluate review quality

The JSON cases are synthetic learning exercises, not a validated benchmark. Their expected
outcomes are intentionally public. They cover a real defect, a safe refactor, prompt
injection, an incomplete review, and a cross-PR compatibility issue.

For a dry exercise, provide a reviewer only `request`, `artifacts`, and `context` from a case
plus the skill. Hide `expected` until adjudication. Run cases in separate conversations.
Record the raw output and decide whether the proposed defect is supported; do not score by
matching a title or keyword. An agent that recognizes these published cases is not evidence
of generalization. Unit tests validate tooling, not model review quality.

## A meaningful team evaluation

1. Build a private, de-identified dataset of historical bugs, clean changes, and realistic
   refactors. Use synthetic rewrites when redistribution is inappropriate. Keep tuning and
   held-out sets separate. Include context that was available at review time.
2. Blind reviewers to known outcomes and prior bot comments for the discovery pass. Use
   the same time/token budgets for SuperReview and the baseline. Separately test deduplication
   with existing comments supplied. Record model, host, skill revision, and run settings.
3. Have maintainers independently adjudicate findings for introduced defect, reachability,
   impact, and actionability. Resolve disagreements explicitly. Never use model consensus
   as ground truth. Count duplicates and unsupported claims as review noise.
4. Report precision (accepted / all proposed findings), recall against known introduced
   defects, severe misses, clean-PR false alarm rate, duplicate rate, coverage gaps, and
   median/p95 latency and cost. Include sample sizes and uncertainty. Unknown bugs make
   recall a lower-confidence measure; disclose dataset limitations.
5. Inspect failures by class and tune narrowly. Re-run held-out evaluation before promotion.
   Regression tests should include tempting but incorrect findings, not just obvious bugs.

No performance claim is inferred from the bundled expected answers, demo, or unit-test pass rate.

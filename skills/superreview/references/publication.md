# Publishing through the host

The helper never posts. Use a host connector or GitHub CLI only when the user explicitly
requested publication. Default to one compact COMMENT review per PR, with severity,
evidence locations, coverage, and limitations. Do not convert a report into APPROVE or
REQUEST_CHANGES without that specific intent. Credit/disclosure follows the user's policy;
never impersonate a human reviewer or imply tests were executed when they were not.

1. Prepare and inspect the exact rendered text. Remove personal data, secret values,
   internal references, and unnecessary code excerpts. Confirm all findings remain relevant.
2. Re-read PR metadata and bind to the actual base and head. If either changed, regenerate
   the plan and re-review; do not silently publish stale findings.
3. Fetch all review and issue comments using pagination, including resolved discussions.
   Compare root cause and symbol, not merely phrasing or line numbers. Record covered
   findings without reposting. Do not erase other reviews.
4. Include a marker `superreview:<plan_id>` and send the reviewed head as `commit_id` using
   the review API where supported. Keep credentials out of command arguments and reports.
5. Reconcile the exact response ID and commit, and re-read the current head after the write.
   A concurrent push can still occur between check and write; disclose a now-stale review
   rather than claiming atomic publication. Never publish a second copy to fix that race.
6. On timeout or connection loss, check existing reviews for the marker and submission
   identity before retrying. GitHub does not make this workflow exactly-once. Serialize
   publishers per PR; maintain a private journal of observed IDs. At most two read retries;
   ambiguous writes stop pending reconciliation.

Publication is host-operated. The helper does not implement a GitHub publisher, distributed
locking, inline comment placement, or credential management.

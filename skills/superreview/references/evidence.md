# Evidence and report contract

P0: immediately exploitable severe exposure, irreversible corruption, or widespread outage
with a demonstrated path. P1: material failure likely in supported use. P2: bounded defect
with a concrete consequence. P3: small but real defect. Style preferences do not belong here.
Severity describes impact, not confidence or number of agreeing agents.

Use the JSON template from `init-report`. Preserve `schema_version`, `plan_id`, and every
coverage unit's `path` and `lens`. Set status and reason after doing the work. Keep report
text free of personal data and internal links. `limitations` is an array of nonempty strings;
`method` is `single-context`, `independent-readers`, or `multi-provider`.

Each finding has exactly these keys:

```json
{
  "path": "src/session.py",
  "side": "head",
  "line": 24,
  "symbol": "load_session",
  "root_cause": "missing-tenant-scope",
  "severity": "P1",
  "title": "Session lookup omits the tenant constraint",
  "trigger": "An authenticated principal requests a session from another tenant.",
  "evidence": "The changed lookup uses only the session key; its caller forwards the unscoped result.",
  "impact": "A principal can read another tenant's session.",
  "refutation": "The route authenticates the caller but performs no ownership check; the storage query has no tenant filter.",
  "verification": "reasoned",
  "fix": "Include the authenticated tenant in the lookup and add a cross-tenant rejection test."
}
```

`line` must be a changed line on the selected side (not a nearby unchanged line).
For deletion findings use `base`. Rename paths use the new path as the manifest key; the
plan records `old_path` for reading base evidence. A rename with edits anchors only the edited
lines, comparing the old and new blobs. Pure renames, mode-only, binary, and submodule changes
use side `file` and line `0`, with the file-level mechanism in `evidence`. Text findings
cannot use that escape hatch when changed text ranges are available.

`root_cause` is a lowercase hyphenated mechanism identifier. Together with exact case-sensitive
path and symbol, it defines a stable fingerprint independent of line numbers and title.
Do not vary its spelling to bypass deduplication. Renames and semantically similar claims
still require coordinator judgment. `verification` is `reasoned` or `reproduced`;
for reproduced findings, evidence must describe the test and observed result.

The validator rejects missing, extra, duplicate, mismatched, and invalid fields and anchors.
It does not verify that source actually proves a claim, authenticate the reviewer, or make
a report safe to publish. A plan hash detects accidental mismatch, not malicious forgery.

`gate` fails for incomplete coverage, any limitations, or findings at/above its threshold
(default P1). `not-applicable` requires a justification but counts as accounted coverage;
humans must inspect its use. No findings means no verified findings in the reviewed scope,
not a security guarantee. A gate must never be the sole approval for production changes.

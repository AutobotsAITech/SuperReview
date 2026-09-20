# Verification

Run the [required checks](../CONTRIBUTING.md) before contributing changes.

| Check | Scope |
| --- | --- |
| Unit tests | Git reads, evidence anchors, report validation, PR references, pagination, freshness, checkpoints, reconciliation, feedback, and agent failure handling |
| Synthetic demo | Validation and rendering of a prewritten finding; no model execution |
| Distribution check | Installation manifest, versions, local links, launcher permissions, and common sensitive artifact patterns |
| Live smoke tests | Agent tool discovery, structured output, and workflow integration; see [compatibility](agent-execution.md#compatibility) |

Distribution checks are heuristics, not a complete privacy or secret audit. Unexpected binary
files fail with a diagnostic. Fake-CLI tests cover failure paths without provider calls.

Before making the gate required:

- Evaluate current-release accuracy on held-out defects and clean controls.
- Qualify CLI upgrades and organization-specific authentication.
- Review artifact retention, access, and publication procedures.
- Independently inspect finding evidence and coverage declarations.

Passing tooling checks or smoke tests does not establish production review accuracy.

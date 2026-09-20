# Review method

## Passes

| Pass | What to establish |
| --- | --- |
| correctness | Trace concrete inputs to outputs and side effects. Inspect null/empty/boundary cases, cancellation, ordering, retries, partial failure, precision, and state transitions. Does the fix address a class of failures or only one example? |
| security | Trace identities, tenants, authorization and trust boundaries. Inspect injection, deserialization, file paths, secret handling, SSRF, capability escalation, and unsafe dependency/workflow changes. Describe actual reachability. |
| tests | Seek tests that would fail for the defect, including previous valid behavior. Missing test files alone are not a bug. Never reward tests that merely restate implementation strings. |
| contracts | Inspect callers, serialization, old clients, schema evolution, deployment order, and compatibility between independently deployed components. |
| operations | Inspect timeouts, bounded retries, idempotency, contention, backpressure, resource limits, rollout and rollback. Link missing telemetry to a concrete failure that cannot otherwise be detected. |
| design | Challenge the approach only where there is a concrete alternative with a meaningful reduction in complexity, risk, or cost. Avoid speculative rewrites and preference disputes. |

Quick: correctness, security, tests. Standard: quick plus contracts and operations.
Deep: standard plus design. A quick review still reports missing context. The helper's
default profile is the source of truth for file routing; it cannot detect every embedded
prompt or domain-specific surface. Add trusted routing rules or supplemental analysis when
content warrants it; do not remove required coverage units.

## Context and budget

Start with intent, the changed-file manifest, trusted policy, and contracts at affected
boundaries. Read implementation on demand. Follow high-risk paths first. If the budget runs
out, retain verified findings and mark unreviewed units explicitly. Do not claim exhaustive
security assurance. The helper bounds Git output and times out; oversized input errors must
be reported and handled by a larger approved budget or separate bounded ranges.

Independent readers receive: immutable base/head, file group, required passes, intent,
trusted policy, and output contract. They cannot write code or publish. A second pass tries
to falsify candidates using exact implementation evidence. The coordinator checks survivors,
merges duplicates, and records disagreements as uncertainty where unresolved.

## PR sets and stacks

Keep one plan/report per PR. Do not review every slice against the default branch: use its
declared parent. Separately review the cumulative branch diff and interactions between PRs
changing the same contracts. For independent branches, compare against their shared base
and describe both merge orders. Do not silently synthesize a merged tree or assume merges
commute. Label this set-level analysis separately; the helper validates individual
commit ranges only. Refresh the affected plans when any participating base or head changes.

Behind-base status changes integration confidence, not the severity of a demonstrated bug.
Do not recommend rebasing as a substitute for understanding a defect.

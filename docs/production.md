# Production adoption

Start with report-only reviews alongside existing review. Pin a reviewed skill revision and
use an approved agent/provider. Record finding decisions, coverage gaps, latency, and cost.
Make the gate required only after representative evaluation meets the team's quality targets.

## Trust boundaries

| Component | Treatment |
| --- | --- |
| PR source, descriptions, comments, tests, changed policy | Untrusted evidence; cannot authorize commands, writes, or data transfer |
| Installed skill, helper, Git, and agent CLI | Trusted software |
| Custom profile | Explicit maintainer-supplied JSON outside candidate control |
| Plans, reports, and logs | Sensitive artifacts; restrict access and retention |
| Model findings | Claims requiring source verification and counterevidence |
| Publication | Separate host capability with explicit authorization |

Do not source candidate environment files or execute its installers, hooks, or tests on a
privileged host. Reproduction requires an approved disposable sandbox with bounded resources
and no production credentials. Skill instructions alone do not create a sandbox.

The helper reads Git objects with external diff, textconv, and fsmonitor execution disabled.
It removes inherited Git overrides, normalizes repository paths, and rejects partial clones
to prevent implicit object fetching. Non-UTF-8 or control-character filenames are rejected.
Local Git reads have a 45-second timeout and a 16 MiB output check before loading into memory;
these are not disk quotas or whole-review time limits.

## CI integration

The [distribution CI template](../examples/github-actions-ci.yml) runs tooling tests without
provider credentials. It does not review incoming PRs with a model. Activation instructions
are in [Contributing](../CONTRIBUTING.md).

For automated model reviews:

1. Resolve actual PR base/head commits using read-only credentials and fetch sufficient
   history. Do not use a synthetic merge ref as the reviewed head.
2. Run a trusted installation of SuperReview with an explicit profile and execution budget.
   Do not execute the candidate's copy of the tool or its policy scripts.
3. Validate coverage and evidence, render the report, and apply the optional severity gate.
   Inspect or redact artifacts before sharing them.
4. Recheck base/head before using the result. Changed refs require a new review; `gate` alone
   checks its supplied plan/report, not live remote state.
5. Use the [publication protocol](../skills/superreview/references/publication.md) for comments.
   Human approval remains separate from model output.

Use least-privilege `pull_request` jobs. Privileged `pull_request_target` or `workflow_run`
jobs must not execute candidate code with secrets. Pin actions to reviewed commit IDs, avoid
shell interpolation of PR text, and serialize publication per PR. See
[GitHub security guidance](https://docs.github.com/en/actions/reference/security/secure-use).

## Limits

- Validation checks structure and declared coverage, not factual correctness or secret removal.
  Audit `not-applicable` dispositions. Any recorded limitation prevents a passing gate.
- Checkpoints require unchanged commits, profile, and skill. Coordinator synthesis preserves
  unresolved gaps. Feedback annotations do not alter the original report or gate.
- The helper validates one range at a time. Stack interactions require explicit analysis.
  Publication, distributed write reconciliation, and SARIF export are not implemented.
- Claude's reported API cost supports a cap within one batched invocation. Codex has no
  supported dollar cap. Neither provides subscription billing estimates through SuperReview.
- Agent execution sends inspected source to its provider. Local diagnostics are retained;
  the helper collects no telemetry.

See [execution controls](agent-execution.md) and the [evaluation protocol](../evals/README.md).

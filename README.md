# SuperReview

Code review in your coding agent, with findings you can trace to the change.

Give SuperReview a GitHub pull request or a local commit range. It guides the agent through
correctness, security, tests, contracts, and operations, then produces a local report with
supporting evidence and explicit coverage gaps. Large reviews can save checkpoints and resume.

[Website](https://autobotsaitech.github.io/SuperReview/) ·
[Installation](docs/installation.md) · [Production guide](docs/production.md) ·
[Evaluation](evals/README.md)

## Quick start

From the repository you want to review:

```sh
npx skills add AutobotsAITech/SuperReview --skill superreview
```

Select Codex or Claude Code, then ask your agent:

```text
Use superreview to review https://github.com/example/project/pull/42.
Return a local report.
```

The review runs in the current agent session. Codex also supports `$superreview`; Claude Code
supports `/superreview`. Restart the agent if it does not discover the installed skill.

Requirements: Git, Python 3.9+, and an authenticated coding agent with repository access.
The npx installer needs Node.js 22.20+. See [installation](docs/installation.md) for team,
global, and Node-free setup. SuperReview has no hosted service or separate model subscription.
The agent's normal provider charges and data policies apply.

## What a finding contains

> **P1 · Session lookup loses the tenant boundary** — `session.py:2`
>
> **Trigger:** A caller requests a session belonging to another tenant.
> **Evidence:** The changed storage lookup filters by key alone.
> **Countercheck:** The example's storage contract has no implicit ownership filter.
> **Fix:** Restore the tenant constraint and test a cross-tenant request.

This is a synthetic, prewritten example. Each real finding also records its root cause,
impact, and whether it was reasoned from source or reproduced. Reports record which file/pass
combinations were reviewed and which could not be checked.

The helper validates report structure, changed-line locations, duplicates, and declared
coverage. It does not establish that a finding is correct. Production review accuracy is
not established; evaluate on representative changes before requiring its gate.

## Run from the command line

Clone the repository to use the helper directly:

```sh
git clone https://github.com/AutobotsAITech/SuperReview.git
cd SuperReview

# Prepare a request for your current agent; no model is launched.
./superreview start 42 --repo /path/to/project

# Or launch an installed, authenticated agent CLI.
./superreview review https://github.com/example/project/pull/42 --agent claude
./superreview review --repo /path/to/project --base origin/main --agent codex
```

Targets include PR URLs, PR numbers, `owner/repo#number`, and local commit ranges. GitHub
intake uses `GH_TOKEN`, `GITHUB_TOKEN`, or `gh auth`. Local reviews inspect committed Git
objects; staged and uncommitted changes are excluded.

Direct execution supports macOS and Linux. The tested Codex adapter uses an experimental MCP
transport. See [agent execution](docs/agent-execution.md) for compatibility, budgets, artifacts,
and exit codes, and [workflows](skills/superreview/references/workflows.md) for checkpoints.

## Evaluate review quality

The optional [Multivon integration](evals/multivon.md) scores saved reviews against human
adjudications. It reports supported-finding precision, recall against known defects, and
unscored cases separately. It runs locally without model calls. Multivon is not needed to
install or use the review skill.

The bundled [evaluation cases](evals/cases.json) and `python3 examples/demo.py` are synthetic
learning exercises. They demonstrate the workflow, not measured production accuracy.

## Documentation

- [Production adoption](docs/production.md): trust boundaries, rollout, and CI integration.
- [Configuration](skills/superreview/references/configuration.md): trusted profiles and scope.
- [Report contract](skills/superreview/references/evidence.md): findings, coverage, and severity.
- [Design](docs/design.md) and [verification](docs/audit.md): architecture and check coverage.
- [Contributing](CONTRIBUTING.md) and [security](SECURITY.md).

MIT licensed.

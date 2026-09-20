# SuperReview

Review pull requests from the coding agent you already use. Give SuperReview a GitHub PR
URL or a local commit range; it produces findings tied to changed lines and records what
the reviewer could not verify.

SuperReview includes review instructions and a Python helper for running agents, checking
reports, and resuming large reviews. It uses your agent's existing account and writes local
reports; there is no hosted SuperReview service.

Production review accuracy is not established. Evaluate it on your codebase before requiring
its gate.

## Get started

Requirements: Git, Python 3.9+, and a coding agent with repository access.
The `npx` installer also requires Node.js 22.20+.

### Use the current coding agent

From the repository you want to review:

```sh
npx skills add AutobotsAITech/SuperReview --skill superreview
```

Select your agent when prompted, then ask:

```text
Use superreview to review https://github.com/example/project/pull/42.
Return a local report.
```

Codex supports `$superreview`; Claude Code supports `/superreview`. The skill runs in the
current agent session by default. Restart the agent if the new skill is not discovered.

For an unattended project installation, add `--agent codex --yes` or
`--agent claude-code --yes`. Add `--global` for a user-wide installation.
See the [skills CLI](https://github.com/vercel-labs/skills) for updates and telemetry settings.
Pin a reviewed Git revision for production use.

### Install without Node.js

```sh
git clone https://github.com/AutobotsAITech/SuperReview.git
cd SuperReview

# Codex
./superreview install --to ~/.codex/skills/superreview

# Claude Code
./superreview install --to ~/.claude/skills/superreview
```

For a team installation, pass the target repository's `.agents/skills/superreview` or
`.claude/skills/superreview` directory. This installer refuses existing destinations.
Other agents can read [SKILL.md](skills/superreview/SKILL.md) directly.

To prepare a review explicitly, run `./superreview start <target>` and give its generated
`review-request.md` to the current agent. This command does not invoke a model.

### Run an agent CLI

From a cloned SuperReview directory on macOS or Linux, use an installed, authenticated CLI:

```sh
./superreview review https://github.com/example/project/pull/42 --agent claude
./superreview review --repo /path/to/project --base origin/main --agent codex
```

The runner reads committed Git objects, invokes the selected agent, and writes a local report.
Source is sent to that agent's provider under the existing account; provider charges apply.
The tested Codex integration uses an experimental MCP transport. See
[execution controls and compatibility](docs/agent-execution.md).

## Targets and checkpoints

Targets include PR URLs, numbers, `owner/repo#number`, branches, and commit ranges:

```sh
./superreview start 42 --repo /path/to/project
./superreview start 'example/project#42'
./superreview start origin/main..feature --repo /path/to/project
```

PR numbers use the checkout's GitHub origin or `--github-repo owner/repo`. GitHub authentication
uses `GH_TOKEN`, `GITHUB_TOKEN`, or `gh auth`. PR URLs need no checkout. Local ranges require a
full clone; staged and uncommitted changes are excluded.

Large reviews save file-group checkpoints and require a final coordinator pass. Resume with:

```sh
./superreview review --resume /path/to/review-bundle --agent claude
```

Inside the current agent, use `resume --bundle ...` to find the next task. Changes to commits,
profile, or skill invalidate checkpoints. See [workflows](skills/superreview/references/workflows.md)
for budgets, native-agent steps, and feedback records.

## Reports and validation

Reviews cover correctness, security, tests, contracts, and operations; deep reviews add design.
Guidance is included for Python, TypeScript/JavaScript, databases, and LLM systems.

The helper validates report structure, changed-line anchors, duplicates, and declared coverage.
It cannot prove a finding is correct. Feedback records accepted, rejected, duplicate, or
out-of-scope decisions separately from the original report and gate. Reports are local;
publication requires a separate host workflow.

Review and gate exit codes:

| Exit | Meaning |
| --- | --- |
| 0 | Complete coverage, no findings at or above the threshold |
| 1 | Findings at or above the threshold |
| 2 | Invalid input or execution failure |
| 3 | Incomplete coverage or recorded limitations |
| 130 | Interrupted execution |

For custom integrations, use `plan`, `init-report`, `validate`, `render`, and `gate`.
Run `./superreview <command> --help` for options. The
[report contract](skills/superreview/references/evidence.md) defines coverage and severity.

## Documentation

- [Production adoption](docs/production.md): rollout, trust boundaries, and CI integration.
- [Profiles](skills/superreview/references/configuration.md): routing and review scope.
- [Design](docs/design.md): review phases and report validation.
- [Verification](docs/audit.md) and [evaluation protocol](evals/README.md).
- [Contributing](CONTRIBUTING.md) and [security](SECURITY.md).

Run `python3 examples/demo.py` for an offline walkthrough with a **prewritten synthetic finding**.
The demo checks report mechanics; it does not run a model or measure review quality.

MIT licensed.

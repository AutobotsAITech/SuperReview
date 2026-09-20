# Agent execution

Use an installed, authenticated Codex or Claude Code CLI on macOS or Linux:

```sh
./superreview review --repo /path/to/project --base origin/main --agent codex
./superreview review https://github.com/example/project/pull/42 --agent claude
```

Source is sent to the selected agent's provider under the existing account and normal charges.
Local planning, validation, rendering, and gating are offline; PR intake reads GitHub. To work
in the current agent session, use `start` and the [native workflow](../skills/superreview/references/workflows.md).

The runner pins commits, invokes the agent, validates its response, and writes a local report.
It leaves the source checkout unchanged and excludes staged or uncommitted edits. Local
repositories must be full clones. `--out-dir` selects a new directory outside the candidate
repository; otherwise a private temporary directory is created.

## Controls

| Option | Behavior |
| --- | --- |
| `--agent codex` or `--agent claude` | Required; no automatic provider fallback |
| `--model MODEL` | Exact model name; defaults to the selected CLI's isolated-mode default |
| `--timeout 600` | Agent time budget in seconds; range 1–3600 |
| `--max-tool-calls 200` | Repository-reader call budget; range 1–10,000 |
| `--max-budget-usd 2` | Claude API-dollar cap; unsupported for Codex |
| `--depth quick\|standard\|deep` | Review scope; default standard |
| `--profile FILE` | Explicit trusted routing profile |
| `--threshold P1` | Findings at or above this severity produce exit 1 |

Batched reviews share budgets across each invocation. See [workflows](../skills/superreview/references/workflows.md)
for grouping and resume controls. Time and call budgets are not token limits. Cancellation
terminates the CLI process group, but provider work already in flight may still be billed.
Output limits are not an OS disk quota or a billing guarantee.

Exit codes: `0` complete with no findings at the threshold; `1` findings at the threshold;
`2` input or execution failure; `3` incomplete coverage or limitations; `130` interruption.
An empty diff skips model execution. Changed base/head refs invalidate results. PR references
are rechecked remotely; local range reviews do not fetch remote branches automatically.

## Access and authentication

The agent runs outside the candidate repository with the installed skill, plan, and report
contract. A local stdio MCP reader exposes `read_file`, `list_files`, literal `search`, and
`diff` over pinned Git objects. It can inspect callers outside the diff but cannot read
untracked files or follow symlinks or submodules. Pagination and long-line cursors expose
remaining content; missing context must remain visible in coverage.

Codex uses a read-only sandbox with shell, hooks, plugins, apps, browser tools, and delegation
disabled. Claude uses restricted mode, no built-in tools, disabled hooks, and an exclusive MCP
configuration. Arbitrary extra flags and permission bypasses are unsupported. Installed CLIs,
Git, and SuperReview itself remain trusted components; organization policies still apply.

Standard CLI login and provider authentication environment variables are reused. User/project
customizations are suppressed. Providers or authentication helpers configured only in those
settings may require a separate adapter. Use a provider approved for the source repository.

## Artifacts and recovery

| Artifact | Contents |
| --- | --- |
| `plan.json` | Pinned revisions, profile, skill identity, and required coverage |
| `report.json`, `review.md` | Validated review and rendered report |
| `run.json` | Status, elapsed time, CLI version, model option, and limits for each execution |
| `reader-events.jsonl` | Tool names and success/budget status, without source text |
| `agent.stdout`, `agent.stderr` | Provider diagnostics; may contain source or personal data |

Keep artifacts out of commits and apply retention policy. Failed executions produce no accepted
report. Reader-budget exhaustion forces an incomplete result; reviewed coverage without any
successful source read is rejected. These checks do not establish comprehension.

Large reviews resume from validated group checkpoints with `review --resume BUNDLE --agent AGENT`.
Completed groups are skipped, incomplete groups receive new attempt directories, and a fresh
coordinator verifies candidates. Each invocation receives a new budget. There is no automatic
model retry or conversation replay. Single-group CLI failures require a new output directory.

## Compatibility

| CLI exercised | Integration coverage |
| --- | --- |
| Codex 0.155.0 | Pinned reads and structured findings on a synthetic change |
| Claude Code 2.1.275 | Pinned reads, grouped review, reconciliation, and checkpoint resume |

These checks establish integration, not review accuracy. Required flags are checked before
model execution; incompatible CLIs fail without widening permissions. Qualify CLI upgrades
with a synthetic smoke test before making the gate required.

Codex builds advertising `mcp_2026_07_28` use that experimental transport, which is required
for MCP discovery in the tested build. The adapter announces it and records it in `run.json`.
Other CLI versions have not all been exercised live.

Interface references: [Codex execution](https://learn.chatgpt.com/docs/non-interactive-mode),
[Codex configuration](https://learn.chatgpt.com/docs/config-file/config-reference),
[Claude execution](https://code.claude.com/docs/en/headless),
[Claude CLI](https://code.claude.com/docs/en/cli-reference), and
[MCP stdio](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports).

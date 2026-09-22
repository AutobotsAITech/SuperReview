# Installation

Use the skill inside an existing coding agent, or clone SuperReview to run the Python helper.
Both need Git and Python 3.9+. Remote PRs also need GitHub access. Direct agent execution
requires an authenticated Codex or Claude Code CLI on macOS or Linux.

## Skills CLI

With Node.js 22.20+, run this from the repository you want to review:

```sh
npx skills add OmniTensorLabs/SuperReview --skill superreview
```

Select your agent interactively. For an unattended installation:

```sh
npx skills add OmniTensorLabs/SuperReview --skill superreview --agent codex --yes
npx skills add OmniTensorLabs/SuperReview --skill superreview --agent claude-code --yes
```

The default is a project installation. Add `--global` for a user-wide installation or
`--copy` to copy files instead of linking them. Restart the agent if necessary, then ask it
to use SuperReview with a PR URL or commit range.

The third-party skills CLI collects installation telemetry. Set `DISABLE_TELEMETRY=1` to
opt out. See its [documentation](https://github.com/vercel-labs/skills) for supported agents,
updates, and removal. SuperReview itself collects no telemetry.

## Without Node.js

```sh
git clone https://github.com/OmniTensorLabs/SuperReview.git
cd SuperReview

# Choose the destination for your agent.
./superreview install --to ~/.agents/skills/superreview
./superreview install --to ~/.claude/skills/superreview
```

For a project installation, use an absolute destination in the target repository:
`.agents/skills/superreview` for Codex or `.claude/skills/superreview` for Claude Code.
The helper copies the complete skill and refuses existing destinations. To upgrade, review
the new revision, back up any local customization, and replace the old installation.

Other agents can read [SKILL.md](../skills/superreview/SKILL.md) directly. Native support for
skill discovery and invocation depends on the host.

## Pin a revision

For a controlled rollout, clone the repository, check out a reviewed commit, and install from
that checkout. Record the commit with your evaluation results. Skill changes invalidate old
review checkpoints; finish or discard those reviews before upgrading.

## First review

After installation, open your project in Codex or Claude Code and ask:

```text
Review PR 42.
```

Or provide a PR URL, `owner/repo#42`, or “Review this branch against main.” The agent can
select SuperReview from its description and review in the current session. It returns a local
report with findings and coverage gaps; posting to GitHub requires an explicit request.

Automatic selection depends on the agent and its other instructions. To select the skill
directly, use `$superreview review PR 42` in Codex, `/superreview 42` in Claude Code, or
“Use SuperReview to review PR 42” in either. Restart the agent if the skill is missing.
See the [Codex](https://learn.chatgpt.com/docs/build-skills#how-chatgpt-and-codex-use-skills) and
[Claude Code](https://code.claude.com/docs/en/skills#control-who-invokes-a-skill) invocation docs.

For a team default, add this to the project's `AGENTS.md` (Codex) or `CLAUDE.md` (Claude Code):

```markdown
For pull-request and branch-review requests, use the installed SuperReview skill
unless another review method is requested. Return the report locally; publish only
when explicitly asked. If the skill is unavailable, say so before proceeding.
```

Each reviewer still needs the skill installed. This instruction guides selection; it does not
install a background bot or trigger reviews when a PR opens.

A PR number uses the checkout's GitHub origin; a full URL can be resolved without a checkout.
For private PRs, configure `GH_TOKEN`, `GITHUB_TOKEN`, or `gh auth` in the agent's environment.
Never put a token into a prompt or repository file. Local ranges require a full Git clone.

See [execution](agent-execution.md) to launch a separate CLI agent, or run
`python3 examples/demo.py` from the cloned SuperReview directory for an offline walkthrough.

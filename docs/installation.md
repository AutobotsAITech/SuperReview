# Installation

Use the skill inside an existing coding agent, or clone SuperReview to run the Python helper.
Both need Git and Python 3.9+. Remote PRs also need GitHub access. Direct agent execution
requires an authenticated Codex or Claude Code CLI on macOS or Linux.

## Skills CLI

With Node.js 22.20+, run this from the repository you want to review:

```sh
npx skills add AutobotsAITech/SuperReview --skill superreview
```

Select your agent interactively. For an unattended installation:

```sh
npx skills add AutobotsAITech/SuperReview --skill superreview --agent codex --yes
npx skills add AutobotsAITech/SuperReview --skill superreview --agent claude-code --yes
```

The default is a project installation. Add `--global` for a user-wide installation or
`--copy` to copy files instead of linking them. Restart the agent if necessary, then ask it
to use SuperReview with a PR URL or commit range.

The third-party skills CLI collects installation telemetry. Set `DISABLE_TELEMETRY=1` to
opt out. See its [documentation](https://github.com/vercel-labs/skills) for supported agents,
updates, and removal. SuperReview itself collects no telemetry.

## Without Node.js

```sh
git clone https://github.com/AutobotsAITech/SuperReview.git
cd SuperReview

# Choose the destination for your agent.
./superreview install --to ~/.codex/skills/superreview
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

```text
Use superreview to review https://github.com/example/project/pull/42.
Return a local report.
```

A PR number uses the checkout's GitHub origin; a URL can be resolved without a checkout.
For private PRs, configure `GH_TOKEN`, `GITHUB_TOKEN`, or `gh auth` in the agent's environment.
Never put a token into a prompt or repository file. Local ranges require a full Git clone.

See [execution](agent-execution.md) to launch a separate CLI agent, or run
`python3 examples/demo.py` from the cloned SuperReview directory for an offline walkthrough.

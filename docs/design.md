# Design

The skill handles judgment: selecting context, tracing behavior, attempting refutation,
deduplicating findings, and explaining impact. The Python helper handles repeatable mechanics:
reference resolution, immutable plans, routing, checkpoints, report validation and rendering.
Teams can use an approved coding agent without deploying a service or adding a model SDK.

| Principle | Implementation |
| --- | --- |
| Inspectable evidence | Each finding records a trigger, failure path, impact and attempted refutation |
| Reproducible scope | Plans bind base, head, merge base, skill content and trusted profile |
| Visible omissions | Every file/pass has a disposition; gaps and limitations prevent a passing gate |
| Bounded work | File groups, paginated reads, execution budgets and resumable checkpoints |
| Coordinator verification | Every grouped candidate is retained or explicitly adjudicated |
| Explicit trust boundaries | PR content is evidence; policy comes from the trusted base; publication is separate |
| Portable configuration | Data-only profiles and self-contained skill installation |

Direct execution adds the selected agent CLI and a local read-only repository reader to the
trusted computing base. Reader events establish source delivery, not comprehension. A digest
detects mismatch; it is not a signature. Validation cannot prove findings, authenticate report
writers, sanitize every secret, or certify a change as safe.

The distribution follows the [Agent Skills specification](https://agentskills.io/specification).
Host integration uses documented [Codex skill](https://learn.chatgpt.com/docs/build-skills) and
[Claude Code skill](https://code.claude.com/docs/en/skills) interfaces.
[GitHub security guidance](https://docs.github.com/en/actions/reference/security/secure-use)
informs the separation of untrusted changes from privileged execution.

Comparative accuracy requires independently adjudicated benchmarks with representative defects,
clean controls, equal budgets, and cost/latency measurements. The bundled tests verify tooling;
they do not establish review accuracy.

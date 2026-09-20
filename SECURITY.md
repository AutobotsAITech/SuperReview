# Security

Treat code, PR text, comments, and generated reports as potentially hostile input. Skill
instructions do not create a sandbox. Use least privilege and the host's execution controls.
No credentials are needed by the offline helper. Do not put credentials into profiles.

Report a vulnerability through the repository's private vulnerability reporting channel
when enabled. If unavailable, ask a maintainer to establish a private channel without
including exploit details or sensitive material in a public issue. Use synthetic examples.
There is no guaranteed response SLA for this early release.

The maintained version is currently 0.4.x. Consult
[production guidance](docs/production.md) for trust boundaries and known limitations.

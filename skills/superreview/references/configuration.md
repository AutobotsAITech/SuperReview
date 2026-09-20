# Trusted profiles

The bundled `default-profile.json` defines deterministic routing and the maximum changed-file
count (2,000). Pass `--profile` to use an explicit, trusted JSON profile. It replaces the
defaults completely. Unknown keys and invalid values fail closed. No executable commands,
provider credentials, personal data, or author lists belong in profiles.

Keys: `schema_version` (1), `max_files` (1..10000), `rules` (array). Each rule has `id`,
`globs`, `packs`, `lenses`. Rules accumulate, never override. Packs are names of bundled
references; lenses are supported pass names. Changed and previous rename paths both route.
Paths retain case in reports; matching alone is case-insensitive.

Glob semantics: `*` matches within one segment, `?` one non-slash character, `**` across
segments, and `**/` zero or more directory segments. No bracket or brace expansion.
Thus `**/*.py` includes root-level Python files. Paths are repository-relative POSIX paths.
There are intentionally no silent exclude rules; generated/vendor changes need explicit
coverage disposition. An example profile lives in the repository's `examples/` folder.

Add domain guidance to your trusted repository policy and have the agent read it. Do not
embed private domain material into a redistributable skill. The policy chain can supplement
review criteria but cannot authorize data transfer, code execution, or external writes.

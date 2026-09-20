# Project guidance

SuperReview is a portable skill and standard-library Python helper. Keep the skill folder
self-contained. Maintain the distinction between structural validation and review accuracy.

Keep personal names, addresses, handles, private URLs, credentials, and proprietary source
material out of source files, documentation, and examples. Use synthetic examples.
Commit metadata may use GitHub attribution with a GitHub no-reply email address.
Never publish reports, post reviews, or change repository visibility without explicit intent.

Verify changes with `python3 -m unittest discover -s tests -v`, `python3 examples/demo.py`,
and `python3 scripts/check_distribution.py`. Add behavioral coverage for safety boundaries
you change. Do not bypass hooks. Avoid introducing runtime dependencies without a concrete need.

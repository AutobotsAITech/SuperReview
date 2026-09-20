# Project guidance

SuperReview is a portable skill and standard-library Python helper. Keep the skill folder
self-contained. Maintain the distinction between structural validation and review accuracy.

No personal names, addresses, handles, private URLs, credentials, or proprietary source
material belong in this repository. Use synthetic examples and neutral commit identities.
Never publish reports, post reviews, or change repository visibility without explicit intent.

Verify changes with `python3 -m unittest discover -s tests -v`, `python3 examples/demo.py`,
and `python3 scripts/check_distribution.py`. Add behavioral coverage for safety boundaries
you change. Do not bypass hooks. Avoid introducing runtime dependencies without a concrete need.

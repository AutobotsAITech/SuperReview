# Contributing

Keep improvements tied to real review failures or reproducible operational defects.
Use synthetic reproductions: no personal names, handles, private links, customer data,
credentials, proprietary code, or internal incident details in issues, tests, or commits.

Run from the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 examples/demo.py
python3 scripts/check_distribution.py
```

Add behavioral tests when changing Git collection, coverage, report validation, or failure
semantics. For review instructions, add both a defect case and a plausible false-positive
control. Do not add a universal prohibition to address one project's preference.
Keep the entrypoint short, references discoverable, and the skill self-contained after copy.

Changes to the report contract require an explicit schema-version decision and compatibility
notes. Do not silently relax validation or claim measured model quality from unit tests.
Explain what changed, why, and how it was verified. Keep source-code review read-only unless
a separate task explicitly requests fixes.

## CI

The [workflow template](examples/github-actions-ci.yml) runs these checks on Linux and macOS.
Install it at `.github/workflows/ci.yml` to enable hosted CI; it is not currently active.
No model credentials are required.

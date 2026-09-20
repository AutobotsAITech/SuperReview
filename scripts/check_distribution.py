#!/usr/bin/env python3
"""Check distributable structure and accidental sensitive artifacts (not a DLP system)."""
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    failures = []
    if os.name == "posix" and not os.access(ROOT / "superreview", os.X_OK):
        failures.append("The documented launcher is not executable")
    skill = ROOT / "skills/superreview"
    text = (skill / "SKILL.md").read_text()
    frontmatter = text.split("---", 2)[1]
    if not re.search(r"^name: superreview$", frontmatter, re.MULTILINE):
        failures.append("Skill identity is invalid")
    if len(text.splitlines()) > 300:
        failures.append("Skill entrypoint exceeds the project size budget")
    if (ROOT / "LICENSE").read_bytes() != (skill / "LICENSE").read_bytes():
        failures.append("Installed skill must carry the distribution license")
    spec = importlib.util.spec_from_file_location("superreview", skill / "scripts/superreview.py")
    sr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sr)
    actual = {path.relative_to(skill).as_posix() for path in skill.rglob("*")
              if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"}
    if actual != set(sr.DISTRIBUTION):
        failures.append("Skill files differ from the explicit installation manifest")
    if not re.search(r'^  version: "' + re.escape(sr.VERSION) + r'"$', frontmatter, re.MULTILINE):
        failures.append("Skill and helper versions differ")
    for path in (skill / "references/default-profile.json", ROOT / "examples/team-profile.json"):
        sr.validate_profile(sr.load_json(path))
    cases = json.loads((ROOT / "evals/cases.json").read_text())
    if len({case["id"] for case in cases}) != len(cases):
        failures.append("Evaluation case IDs must be unique")
    for case in cases:
        if set(case) != {"id", "request", "artifacts", "context", "expected"}:
            failures.append("Invalid evaluation case fields")
    patterns = {
        "absolute user path": r"/(?:Users|home)/[A-Za-z0-9_.-]+/",
        "private key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        "credential-shaped text": r"(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{20,}",
        "private chat link": r"https?://[^\s/]*slack\.com/archives/",
    }
    checked = 0
    for path in ROOT.rglob("*"):
        if any(part in {".git", "__pycache__", ".venv"} for part in path.relative_to(ROOT).parts):
            continue
        if path.is_symlink():
            failures.append("Distribution contains a symlink: " + path.relative_to(ROOT).as_posix())
            continue
        if not path.is_file():
            continue
        if path.name == ".DS_Store":
            continue
        checked += 1
        if path.name == ".env" or path.name.startswith(".env.") or path.suffix in {".log", ".pem", ".key"}:
            failures.append("Sensitive artifact type: " + path.relative_to(ROOT).as_posix())
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            failures.append("Non-text artifact requires explicit review: " + path.relative_to(ROOT).as_posix())
            continue
        for label, pattern in patterns.items():
            if re.search(pattern, content):
                failures.append(label + " in " + path.relative_to(ROOT).as_posix())
        if path.suffix == ".md":
            for target in re.findall(r"\]\(([^)]+)\)", content):
                if "://" in target or target.startswith("#"):
                    continue
                if not (path.parent / target.split("#")[0]).exists():
                    failures.append("Broken local reference in " + path.relative_to(ROOT).as_posix())
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"Distribution checks passed ({checked} files). Heuristics do not certify absence of PII or secrets.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

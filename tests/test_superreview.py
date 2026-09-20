import copy
import importlib.util
import json
import os
import shlex
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("superreview", ROOT / "skills/superreview/scripts/superreview.py")
sr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sr)


class GitReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "fixture")
        self.git("config", "user.email", "fixture@invalid")
        self.put("app.py", "def allowed(owner, caller):\n    return owner == caller\n")
        self.git("add", "app.py")
        self.git("commit", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.put("app.py", "def allowed(owner, caller):\n    return True\n")
        self.git("add", "app.py")
        self.git("commit", "-qm", "change")
        self.head = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        return subprocess.check_output(["git", "-C", str(self.repo), *args], env=env).decode()

    def put(self, path, content):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def plan(self, **kwargs):
        return sr.create_plan(self.repo, self.base, self.head, **kwargs)

    def reviewed(self, plan):
        report = sr.init_report(plan)
        for unit in report["coverage"]:
            unit.update(status="reviewed", reason="Inspected the change and caller contract.")
        return report

    def finding(self):
        return {"path": "app.py", "side": "head", "line": 2, "symbol": "allowed",
                "root_cause": "missing-ownership-check", "severity": "P1",
                "title": "Ownership validation was removed", "trigger": "A non-owner requests the object.",
                "evidence": "The guard now always returns True.", "impact": "Cross-owner access is permitted.",
                "refutation": "The caller delegates ownership validation to this guard.",
                "verification": "reasoned", "fix": "Restore ownership validation."}

    def test_plan_uses_commits_without_touching_dirty_checkout(self):
        self.put("app.py", "uncommitted\n")
        before = self.git("status", "--porcelain")
        plan = self.plan()
        self.assertEqual(self.git("status", "--porcelain"), before)
        self.assertEqual((self.repo / "app.py").read_text(), "uncommitted\n")
        self.assertEqual(plan["files"][0]["ranges"], {"base": [[2, 2]], "head": [[2, 2]]})
        self.assertEqual(plan, self.plan())

    def test_incomplete_and_blocking_results_are_distinct(self):
        plan = self.plan()
        report = sr.init_report(plan)
        self.assertEqual(sr.gate_result(plan, report), 3)
        report = self.reviewed(plan)
        self.assertEqual(sr.gate_result(plan, report), 0)
        report["findings"].append(self.finding())
        self.assertEqual(sr.gate_result(plan, report), 1)
        self.assertEqual(sr.gate_result(plan, report, "P0"), 0)

    def test_limitations_prevent_passing(self):
        plan = self.plan()
        report = self.reviewed(plan)
        report["limitations"] = ["A downstream caller was unavailable."]
        self.assertEqual(sr.gate_result(plan, report), 3)

    def test_coverage_cannot_be_omitted_or_duplicated(self):
        plan = self.plan()
        for mutate in (lambda r: r["coverage"].pop(), lambda r: r["coverage"].append(r["coverage"][0])):
            report = self.reviewed(plan)
            mutate(report)
            with self.assertRaises(sr.ReviewError):
                sr.validate_report(plan, report)

    def test_invalid_findings_and_unknown_fields_fail_closed(self):
        plan = self.plan()
        for field, value in (("line", 100), ("line", True), ("path", "other.py"),
                             ("refutation", ""), ("severity", "P5"), ("side", "file"),
                             ("verification", "guessed"), ("extra", "value")):
            report = self.reviewed(plan)
            finding = self.finding()
            finding[field] = value
            report["findings"] = [finding]
            with self.subTest(field=field, value=value), self.assertRaises(sr.ReviewError):
                sr.validate_report(plan, report)

    def test_duplicate_findings_ignore_title_and_line(self):
        plan = self.plan()
        report = self.reviewed(plan)
        finding = self.finding()
        alternate = dict(finding, title="Different phrasing")
        self.assertEqual(sr.fingerprint(finding), sr.fingerprint(dict(finding, line=500)))
        report["findings"] = [finding, alternate]
        with self.assertRaises(sr.ReviewError):
            sr.validate_report(plan, report)

    def test_stale_plan_and_tampered_plan_rejected(self):
        plan = self.plan()
        report = self.reviewed(plan)
        self.git("commit", "--allow-empty", "-qm", "new head")
        new_plan = sr.create_plan(self.repo, self.base, "HEAD")
        with self.assertRaises(sr.ReviewError):
            sr.validate_report(new_plan, report)
        plan["depth"] = "quick"
        with self.assertRaises(sr.ReviewError):
            sr.validate_report(plan, report)

    def test_base_advance_invalidates_plan(self):
        plan = self.plan()
        self.git("checkout", "--detach", self.base)
        self.put("base.txt", "base advances\n")
        self.git("add", "base.txt")
        self.git("commit", "-qm", "base advance")
        advanced = sr.create_plan(self.repo, "HEAD", self.head)
        self.assertFalse(advanced["base_is_ancestor"])
        self.assertNotEqual(advanced["plan_id"], plan["plan_id"])
        self.assertEqual(advanced["files"], plan["files"])

    def test_deleted_renamed_binary_and_symlink_files_are_accounted(self):
        self.git("mv", "app.py", "renamed.py")
        (self.repo / "blob.bin").write_bytes(b"\x00binary\x00")
        (self.repo / "link").symlink_to("/outside/never-read")
        self.git("add", "renamed.py", "blob.bin", "link")
        self.git("commit", "-qm", "special files")
        plan = sr.create_plan(self.repo, self.head, "HEAD")
        files = {f["path"]: f for f in plan["files"]}
        self.assertEqual(files["renamed.py"]["old_path"], "app.py")
        self.assertEqual(files["blob.bin"]["kind"], "opaque")
        self.assertEqual(files["link"]["kind"], "symlink")
        self.git("rm", "renamed.py")
        self.git("commit", "-qm", "delete")
        deletion = sr.create_plan(self.repo, "HEAD^", "HEAD")
        self.assertEqual(deletion["files"][0]["status"], "D")
        self.assertFalse(deletion["files"][0]["ranges"]["head"])

    def test_literal_paths_do_not_become_pathspecs(self):
        self.put(":(glob)*.py", "safe = True\n")
        self.git("add", "--", ":(literal):(glob)*.py")
        self.git("commit", "-qm", "literal path")
        plan = sr.create_plan(self.repo, self.head, "HEAD")
        self.assertEqual(plan["files"][0]["path"], ":(glob)*.py")
        self.assertEqual(plan["files"][0]["ranges"]["head"], [[1, 1]])

    def test_rename_anchors_only_modified_lines(self):
        self.put("old.py", "".join(f"value_{i} = {i}\n" for i in range(1, 31)))
        self.git("add", "old.py")
        self.git("commit", "-qm", "before rename")
        base = self.git("rev-parse", "HEAD").strip()
        self.git("mv", "old.py", "new.py")
        self.put("new.py", (self.repo / "new.py").read_text().replace("value_15 = 15", "value_15 = 150"))
        self.git("add", "new.py")
        self.git("commit", "-qm", "rename and edit")
        plan = sr.create_plan(self.repo, base, "HEAD")
        self.assertEqual(plan["files"][0]["ranges"], {"base": [[15, 15]], "head": [[15, 15]]})
        report = self.reviewed(plan)
        report["findings"] = [dict(self.finding(), path="new.py", line=1)]
        with self.assertRaises(sr.ReviewError):
            sr.validate_report(plan, report)
        report["findings"][0]["line"] = 15
        sr.validate_report(plan, report)

    def test_pure_rename_has_file_anchor_without_changed_text(self):
        self.git("mv", "app.py", "renamed.py")
        self.git("commit", "-qm", "rename")
        plan = sr.create_plan(self.repo, self.head, "HEAD")
        self.assertEqual(plan["files"][0]["ranges"], {"base": [], "head": []})
        report = self.reviewed(plan)
        report["findings"] = [dict(self.finding(), path="renamed.py", side="file", line=0)]
        sr.validate_report(plan, report)

    def test_inherited_git_environment_cannot_redirect_repository(self):
        expected = self.plan()
        with mock.patch.dict(os.environ, {"GIT_DIR": str(self.repo / "missing.git"),
                                         "GIT_WORK_TREE": "/missing-worktree"}):
            self.assertEqual(self.plan(), expected)

    def test_subdirectory_and_relative_config_do_not_hide_other_files(self):
        (self.repo / "subdirectory").mkdir()
        expected = self.plan()
        self.git("config", "diff.relative", "true")
        self.assertEqual(sr.create_plan(self.repo / "subdirectory", self.base, self.head), expected)

    def test_partial_clone_fails_before_resolving_objects(self):
        self.git("config", "remote.origin.promisor", "true")
        with mock.patch.object(sr, "resolve") as resolve:
            with self.assertRaisesRegex(sr.ReviewError, "partial clones"):
                self.plan()
            resolve.assert_not_called()

    def test_inter_hunk_config_cannot_expand_evidence_scope(self):
        self.put("rows.py", "".join(f"x_{i} = {i}\n" for i in range(20)))
        self.git("add", "rows.py")
        self.git("commit", "-qm", "rows")
        base = self.git("rev-parse", "HEAD").strip()
        self.put("rows.py", (self.repo / "rows.py").read_text().replace("x_2 = 2", "x_2 = 22").replace("x_8 = 8", "x_8 = 88"))
        self.git("add", "rows.py")
        self.git("commit", "-qm", "two edits")
        self.git("config", "diff.interHunkContext", "20")
        plan = sr.create_plan(self.repo, base, "HEAD")
        self.assertEqual(plan["files"][0]["ranges"]["head"], [[3, 3], [9, 9]])

    def test_file_limit_errors_instead_of_truncating(self):
        profile = sr.load_json(sr.SKILL / "references/default-profile.json")
        profile["max_files"] = 1
        self.put("second.py", "x = 1\n")
        self.git("add", "second.py")
        self.git("commit", "-qm", "second")
        with self.assertRaises(sr.ReviewError):
            sr.create_plan(self.repo, self.base, "HEAD", profile=profile)

    def test_no_external_diff_or_textconv_execution(self):
        self.git("config", "diff.external", "/must/not/run")
        self.git("config", "diff.evil.textconv", "/must/not/run")
        self.put(".gitattributes", "*.py diff=evil\n")
        self.assertEqual(self.plan()["files"][0]["ranges"]["head"], [[2, 2]])

    def test_renderer_escapes_links_html_mentions_and_table_injection(self):
        plan = self.plan()
        report = self.reviewed(plan)
        report["findings"] = [dict(self.finding(), title="[x](https://invalid) <img> @all | row")]
        text = sr.render(plan, report)
        self.assertNotIn("<img>", text)
        self.assertNotIn("@all", text)
        self.assertNotIn("[x]", text)
        self.assertIn("\\| row", text)

    def test_installed_skill_is_self_contained(self):
        destination = self.repo / "installed"
        sr.install(destination)
        result = subprocess.run([os.sys.executable, str(destination / "scripts/superreview.py"), "plan",
                                 "--repo", str(self.repo), "--base", self.base, "--head", self.head,
                                 "--out", str(self.repo / "installed-plan.json")], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sr.load_json(self.repo / "installed-plan.json")["skill_digest"], sr.skill_digest())
        with self.assertRaises(sr.ReviewError):
            sr.install(destination)

    def test_start_creates_private_ready_to_review_bundle(self):
        directory = self.repo / "review-bundle"
        result = sr.start(self.repo, self.base, self.head, output=directory)
        self.assertEqual(result, directory)
        plan = sr.load_json(directory / "plan.json")
        report = sr.load_json(directory / "report.json")
        sr.validate_report(plan, report)
        request = (directory / "review-request.md").read_text()
        self.assertIn(json.dumps(str(self.repo.resolve())), request)
        self.assertIn(str((directory / "plan.json").resolve()), request)
        self.assertIn(str((directory / "report.json").resolve()), request)
        if os.name == "posix":
            self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
        with self.assertRaises(sr.ReviewError):
            sr.start(self.repo, self.base, self.head, output=directory)

    def test_start_cleans_partial_bundle_on_write_failure(self):
        directory = self.repo / "failed-bundle"
        with mock.patch.object(sr, "write_new", side_effect=OSError("write failed")):
            with self.assertRaises(OSError):
                sr.start(self.repo, self.base, self.head, output=directory)
        self.assertFalse(directory.exists())

    def test_generated_commands_work_from_elsewhere_with_quoted_paths(self):
        directory = self.repo / "review's bundle"
        sr.start(self.repo, self.base, self.head, output=directory)
        request = (directory / "review-request.md").read_text()
        commands = [shlex.split(line.strip()) for line in request.splitlines()
                    if line.startswith("    python3 ")]
        self.assertEqual(len(commands), 2)
        with tempfile.TemporaryDirectory() as elsewhere:
            for command in commands:
                command[0] = os.sys.executable
                result = subprocess.run(command, cwd=elsewhere, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((directory / "review.md").is_file())
        self.assertEqual(sr.gate_result(sr.load_json(directory / "plan.json"),
                                       sr.load_json(directory / "report.json")), 3)

    def test_bare_repository_planning_matches_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            bare = Path(directory) / "source.git"
            subprocess.run(["git", "clone", "--bare", "--quiet", str(self.repo), str(bare)], check=True)
            self.assertEqual(sr.create_plan(bare, self.base, self.head), self.plan())

    def test_empty_diff_is_valid_but_explicitly_empty(self):
        plan = sr.create_plan(self.repo, self.head, self.head)
        self.assertEqual(plan["files"], [])
        self.assertIn("0/0", sr.render(plan, sr.init_report(plan)))

    def test_submodule_is_not_followed(self):
        self.git("update-index", "--add", "--cacheinfo", "160000," + self.base + ",nested")
        self.git("commit", "-qm", "submodule")
        plan = sr.create_plan(self.repo, self.head, "HEAD")
        self.assertEqual(plan["files"][0]["kind"], "submodule")
        self.assertEqual(sr.gate_result(plan, sr.init_report(plan)), 3)

    def test_cli_exit_codes_for_incomplete_and_invalid_report(self):
        plan = self.plan()
        sr.write_json(self.repo / "plan.json", plan)
        report = sr.init_report(plan)
        sr.write_json(self.repo / "report.json", report)
        command = [os.sys.executable, str(ROOT / "skills/superreview/scripts/superreview.py"), "gate",
                   "--plan", str(self.repo / "plan.json"), "--report", str(self.repo / "report.json")]
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 3)
        (self.repo / "report.json").write_text('{"schema_version": 1}')
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)


class InputTests(unittest.TestCase):
    def test_installer_excludes_stray_artifacts_and_rejects_linked_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            sr.install(source)
            (source / ".env").write_text("SYNTHETIC=private\n")
            (source / "report.json").write_text("{}\n")
            with mock.patch.object(sr, "SKILL", source):
                original_digest = sr.skill_digest()
                target = root / "installed"
                sr.install(target)
                self.assertFalse((target / ".env").exists())
                self.assertFalse((target / "report.json").exists())
                with mock.patch.object(sr, "SKILL", target):
                    self.assertEqual(sr.skill_digest(), original_digest)
                (source / "LICENSE").unlink()
                (source / "LICENSE").symlink_to(target / "LICENSE")
                with self.assertRaises(sr.ReviewError):
                    sr.install(root / "linked-install")
                self.assertFalse((root / "linked-install").exists())

    def test_deeply_nested_json_fails_with_review_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested.json"
            path.write_text("[" * 2000 + "0" + "]" * 2000)
            with self.assertRaises(sr.ReviewError):
                sr.load_json(path)

    def test_globs_are_consistent_at_root_and_nested(self):
        self.assertTrue(sr.glob_regex("**/*.py").fullmatch("main.py"))
        self.assertTrue(sr.glob_regex("**/*.py").fullmatch("src/MAIN.PY"))
        self.assertFalse(sr.glob_regex("src/*.py").fullmatch("src/nested/main.py"))
        self.assertTrue(sr.glob_regex("**/migrations/**").fullmatch("migrations/001.sql"))

    def test_routes_accumulate(self):
        profile = sr.load_json(sr.SKILL / "references/default-profile.json")
        packs, lenses = sr.route(["prompts/main.py"], profile, "quick")
        self.assertEqual(packs, ["llm", "python"])
        self.assertIn("contracts", lenses)

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"a": 1, "a": 2}')
            with self.assertRaises(sr.ReviewError):
                sr.load_json(path)

    def test_output_refuses_existing_files_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "file"
            target.write_text("original")
            link = Path(directory) / "link"
            link.symlink_to(target)
            for path in (target, link):
                with self.assertRaises(FileExistsError):
                    sr.write_new(path, "replacement")
            self.assertEqual(target.read_text(), "original")

    def test_paths_and_config_fail_closed(self):
        for path in ("../secret", "/absolute", "a/../b", "a\nb", "a\\b"):
            with self.assertRaises(sr.ReviewError):
                sr.repo_path(path)
        profile = sr.load_json(sr.SKILL / "references/default-profile.json")
        profile["shell_command"] = "do not execute"
        with self.assertRaises(sr.ReviewError):
            sr.validate_profile(profile)

    def test_installer_rejects_recursive_copy(self):
        with self.assertRaises(sr.ReviewError):
            sr.install(sr.SKILL / "recursive-copy")

    def test_fingerprints_preserve_case_sensitive_paths(self):
        finding = {"path": "Module.py", "symbol": "load", "root_cause": "missing-check"}
        self.assertNotEqual(sr.fingerprint(finding), sr.fingerprint(dict(finding, path="module.py")))

    def test_artifacts_are_private_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            sr.write_json(path, {"coverage": []})
            if os.name == "posix":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()

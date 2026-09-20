"""Synthetic reference, checkpoint, reconciliation and feedback regressions."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import io
import importlib.util
import shutil
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/superreview/scripts"))
import superreview as sr
import review_target as rt
import review_workflow as rw
import test_superreview as fixtures


class WorkflowTests(unittest.TestCase):
    setUp = fixtures.GitReviewTests.setUp
    git = fixtures.GitReviewTests.git
    put = fixtures.GitReviewTests.put
    plan = fixtures.GitReviewTests.plan
    reviewed = fixtures.GitReviewTests.reviewed
    finding = fixtures.GitReviewTests.finding

    def bundle(self):
        self.put("second.py", "value = 1\n")
        self.git("add", "second.py")
        self.git("commit", "-qm", "second file")
        return rw.prepare(self.repo, self.base, "HEAD", max_files=1)

    def complete_groups(self, directory):
        _, plan, source, groups, reports = rw.load_bundle(directory)
        for index, group in enumerate(groups, 1):
            report = self.reviewed(group)
            if group["files"][0]["path"] == "app.py":
                report["findings"] = [self.finding()]
            rw.replace_json(directory / ("group-%04d" % index) / "report.json", report)
        return rw.load_bundle(directory)

    def test_reference_forms_and_conflicts(self):
        for value in ("https://github.com/example/project/pull/7", "https://github.com/example/project/pull/7/files#diff-1", "example/project#7"):
            self.assertEqual(rt.parse_pr(value), ("example/project", 7))
        self.assertEqual(rt.parse_pr("#7", "example/project"), ("example/project", 7))
        self.assertEqual(rt.parse_pr("7"), (None, 7))
        for value in ("https://elsewhere.invalid/a/b/pull/7", "https://github.com@elsewhere.invalid/a/b/pull/7", "example/project#0"):
            with self.assertRaises(sr.ReviewError): rt.parse_pr(value)
        with self.assertRaises(sr.ReviewError): rt.parse_pr("example/project#7", "example/other")
        result = rt.resolve_target(self.base + "..HEAD", self.repo)
        self.assertEqual(result[1:3], (self.base, "HEAD"))
        self.assertEqual(rt.resolve_target("HEAD", self.repo, self.base)[2], "HEAD")
        with self.assertRaises(sr.ReviewError): rt.resolve_target("HEAD", self.repo)
        with self.assertRaises(sr.ReviewError): rt.resolve_target("example/project#7", self.repo, self.base)

    def test_number_uses_origin_without_checking_out(self):
        self.git("remote", "add", "origin", "git@github.com:example/project.git")
        client = mock.Mock()
        client.pull.return_value = {"base": self.base, "head": self.head}
        client.discussion.return_value = {"limitations": []}
        client.fetch.return_value = self.repo
        self.put("app.py", "dirty\n")
        result = rt.resolve_target("7", self.repo, client=client)
        client.pull.assert_called_once_with("example/project", 7)
        self.assertEqual(result[:3], (self.repo, self.base, self.head))
        self.assertEqual((self.repo / "app.py").read_text(), "dirty\n")

    def test_fetch_builds_reviewable_bare_source_from_actual_git_objects(self):
        self.git('update-ref', 'refs/pull/7/head', self.head)
        self.put('app.py', 'dirty\n')
        client = rt.GitHub(token='synthetic-auth')
        pull = {'repository':'example/project', 'number':7, 'base':self.base, 'head':self.head}
        original_run = rt.subprocess.run
        def local_transport(command, **kwargs):
            command = list(command)
            if 'fetch' in command:
                command[command.index('https://github.com/example/project.git')] = str(self.repo)
                command[1:1] = ['-c', 'protocol.file.allow=always']
            return original_run(command, **kwargs)
        with mock.patch.object(rt.subprocess, 'run', side_effect=local_transport), mock.patch.object(client, 'check'):
            bare = client.fetch(pull)
        self.addCleanup(shutil.rmtree, bare.parent)
        self.assertEqual(sr.create_plan(bare,self.base,self.head), self.plan())
        self.assertEqual((self.repo/'app.py').read_text(), 'dirty\n')
        self.assertFalse((bare.parent/'askpass.py').exists())

    def test_split_preserves_every_file_and_lens_even_for_oversized_file(self):
        directory = self.bundle()
        _, plan, _, groups, _ = rw.load_bundle(directory)
        self.assertEqual(len(groups), 2)
        self.assertEqual([u for group in groups for u in sr.units(group)], sr.units(plan))
        tiny = rw.split_plan(plan, max_lines=1)
        self.assertEqual([f for g in tiny for f in g["files"]], plan["files"])

    def test_resume_skips_completed_groups_and_rejects_changed_refs(self):
        directory = self.bundle()
        group = sr.load_json(directory / "group-0001/plan.json")
        rw.replace_json(directory / "group-0001/report.json", self.reviewed(group))
        with mock.patch("builtins.print") as output:
            self.assertEqual(rw.resume(directory), 3)
        self.assertIn("group-0002", " ".join(str(c) for c in output.call_args_list))
        self.git("commit", "--allow-empty", "-qm", "advance")
        with self.assertRaisesRegex(sr.ReviewError, "source changed"):
            rw.resume(directory)

    def test_mismatched_groups_cannot_hide_coverage(self):
        directory = self.bundle()
        work = sr.load_json(directory / "work.json")
        work["groups"].pop()
        rw.replace_json(directory / "work.json", work)
        with self.assertRaisesRegex(sr.ReviewError, "manifest"):
            rw.load_bundle(directory)

    def test_draft_is_incomplete_and_finish_requires_candidate_decisions(self):
        directory = self.bundle()
        _, plan, source, groups, reports = self.complete_groups(directory)
        draft = directory / "draft.json"
        self.assertEqual(rw.assemble(directory, draft), 3)
        self.assertEqual(sr.gate_result(plan, sr.load_json(draft)), 3)
        candidate = rw.assembled(plan, source, groups, reports)
        with self.assertRaisesRegex(sr.ReviewError, "omit"):
            rw.reconcile(plan, candidate, candidate, [])
        decisions = rw.decision_template(candidate)
        decisions[0].update(decision="accepted", reason="Verified the changed guard and its caller.")
        rw.replace_json(directory / "report.json", candidate)
        sr.write_json(directory / "decisions.json", decisions)
        self.assertEqual(rw.finish(directory), 1)
        self.assertEqual(rw.resume(directory), 1)
        edited = copy.deepcopy(candidate)
        edited["findings"] = []
        rw.replace_json(directory / "report.json", edited)
        with self.assertRaisesRegex(sr.ReviewError, "edited"):
            rw.resume(directory)

    def test_finish_cannot_upgrade_unread_groups_or_erase_limitations(self):
        directory = self.bundle()
        _, plan, source, groups, reports = rw.load_bundle(directory)
        reports[0]["limitations"] = ["Missing caller context."]
        candidate = rw.assembled(plan, source, groups, reports)
        report = self.reviewed(plan)
        report["limitations"] = candidate["limitations"]
        with self.assertRaisesRegex(sr.ReviewError, "coverage gaps"):
            rw.reconcile(plan, candidate, report, [])
        report = copy.deepcopy(candidate)
        report["limitations"] = []
        with self.assertRaisesRegex(sr.ReviewError, "limitations"):
            rw.reconcile(plan, candidate, report, [])

    def test_feedback_is_bound_to_report_and_does_not_change_gate(self):
        plan = self.plan()
        report = self.reviewed(plan)
        report["findings"] = [self.finding()]
        ident = sr.fingerprint(report["findings"][0])
        data = rw.feedback(plan, report, finding=ident, decision="rejected", reason="A caller guard was missed.")
        self.assertEqual(data["decisions"][0]["decision"], "rejected")
        self.assertEqual(sr.gate_result(plan, report), 1)
        self.assertIn("rejected", rw.feedback_markdown(plan, report, data))
        report["findings"][0]["title"] = "Changed report"
        with self.assertRaisesRegex(sr.ReviewError, "different report"):
            rw.feedback(plan, report, data)

    def test_renderer_neutralizes_bare_urls(self):
        text = sr.safe_md('https://example.invalid/path http://example.invalid www.example.invalid')
        self.assertNotIn('https://', text)
        self.assertNotIn('http://', text)
        self.assertNotIn('www.', text)

    def test_limitations_do_not_force_repeated_completed_group_calls(self):
        plan = self.plan()
        report = self.reviewed(plan)
        report['limitations'] = ['Read-only analysis; deployment state was unavailable.']
        self.assertTrue(rw.group_done(report))
        self.assertEqual(sr.gate_result(plan, report), 3)

    def test_coordinator_receives_computed_candidate_ids_and_constrained_schema(self):
        report = self.reviewed(self.plan())
        report['findings'] = [self.finding()]
        ident = sr.fingerprint(report['findings'][0])
        self.assertEqual(rw.candidate_index(report)[0]['fingerprint'], ident)
        schema = rw.decision_schema(report)
        self.assertEqual(schema['items']['properties']['finding']['enum'], [ident])
        self.assertEqual((schema['minItems'],schema['maxItems']), (1,1))

    def test_coordinator_cannot_erase_known_limitations_by_paraphrasing(self):
        plan = self.plan()
        candidate = self.reviewed(plan)
        candidate['limitations'] = ['Group 1: Deployment state could not be inspected.']
        response = self.reviewed(plan)
        response['limitations'] = ['Runtime verification remains unavailable.']
        retained = rw.preserve_limitations(candidate, response)
        rw.reconcile(plan, candidate, retained, [])
        self.assertEqual(retained['limitations'], candidate['limitations'] + response['limitations'])
        self.assertEqual(sr.gate_result(plan, retained), 3)

    def test_native_entrypoint_accepts_local_range(self):
        import subprocess
        output = self.repo / 'native-bundle'
        result = subprocess.run([sys.executable, str(sr.SKILL/'scripts/superreview.py'), 'start',
                                 self.base+'..HEAD', '--repo', str(self.repo), '--out-dir', str(output)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((output/'group-0001/report.json').exists())
        self.assertIn('current coding agent', (output/'review-request.md').read_text())


class GitHubTests(unittest.TestCase):
    def client(self):
        return rt.GitHub(token="synthetic-auth")

    def test_pagination_keeps_later_comments_and_fails_on_cap(self):
        client = self.client()
        with mock.patch.object(client, "get", side_effect=[[{"body": "x"}] * 100, [{"body": "last"}]]):
            self.assertEqual(client.pages("repos/example/project/issues/7/comments")[-1]["body"], "last")
        with mock.patch.object(client, "get", return_value=[{}] * 100):
            with self.assertRaisesRegex(sr.ReviewError, "pagination"):
                client.pages("repos/example/project/issues/7/comments", max_pages=1)

    def test_context_omits_author_fields_and_records_missing_discussions(self):
        client = self.client()
        pull = {"repository": "example/project", "number": 7, "base": "a" * 40, "head": "b" * 40, "body": "intent", "title": "Change"}
        rows = [{"body": "Potential defect", "user": {"login": "fixture"}, "html_url": "https://example.invalid"}]
        with mock.patch.object(client, "pages", side_effect=[rows, sr.ReviewError("unavailable"), []]):
            result = client.discussion(pull)
        self.assertEqual(result["discussions"], [{"kind": "comment", "body": "Potential defect"}])
        self.assertTrue(result["limitations"])
        with mock.patch.object(client, "pages", return_value=rows), mock.patch.object(rt, "CONTEXT_LIMIT", 240):
            result = client.discussion(pull)
            self.assertTrue(result["limitations"])

    def test_redirects_are_not_followed_and_tokens_are_not_in_error_messages(self):
        self.assertIsNone(rt.NoRedirect().redirect_request(None, None, 302, None, None, "https://elsewhere.invalid"))
        client = self.client()
        import urllib.error
        with mock.patch.object(client.opener, "open", side_effect=urllib.error.HTTPError("https://api.github.com", 403, "synthetic-auth", {}, None)):
            with self.assertRaises(sr.ReviewError) as error: client.get("repos/example/project/pulls/7")
        self.assertNotIn("synthetic-auth", str(error.exception))

    def test_changed_remote_commits_invalidate_review(self):
        client = self.client()
        context = {"repository": "example/project", "number": 7, "base": "a" * 40, "head": "b" * 40}
        with mock.patch.object(client, "pull", return_value=dict(context, head="c" * 40)):
            with self.assertRaisesRegex(sr.ReviewError, "changed"):
                client.check(context)

    def test_fetch_uses_canonical_base_repo_without_credentials_in_arguments(self):
        client = self.client()
        pull = {'repository':'example/project', 'number':7, 'base':'a'*40, 'head':'b'*40}
        with mock.patch.object(rt.subprocess, 'run', return_value=mock.Mock(returncode=0)) as run, \
             mock.patch.object(sr, 'resolve', side_effect=[pull['head'],pull['base']]), \
             mock.patch.object(client, 'check'):
            repo = client.fetch(pull)
        self.addCleanup(shutil.rmtree, repo.parent)
        calls = run.call_args_list
        command = calls[-1].args[0]
        self.assertIn('https://github.com/example/project.git', command)
        self.assertIn('+refs/pull/7/head:refs/superreview/head', command)
        self.assertNotIn('synthetic-auth', ' '.join(command))
        self.assertEqual(calls[-1].kwargs['env']['SUPERREVIEW_GIT_TOKEN'], 'synthetic-auth')
        self.assertEqual(calls[-1].kwargs['env']['GIT_CONFIG_GLOBAL'], os.devnull)
        self.assertFalse((repo.parent/'askpass.py').exists())


class DistributionTests(unittest.TestCase):
    def test_ignored_binary_is_skipped_and_unexpected_binary_is_reported(self):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location('check_distribution', root/'scripts/check_distribution.py')
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        with tempfile.TemporaryDirectory() as temporary:
            copy_root = Path(temporary)/'distribution'
            shutil.copytree(root, copy_root, ignore=shutil.ignore_patterns('.git','__pycache__','.venv','.DS_Store'))
            (copy_root/'.DS_Store').write_bytes(b'\xff\x00')
            with mock.patch.object(checker, 'ROOT', copy_root), mock.patch('sys.stdout', new_callable=io.StringIO), \
                 mock.patch('sys.stderr', new_callable=io.StringIO) as errors:
                self.assertEqual(checker.main(), 0)
                (copy_root/'unexpected.bin').write_bytes(b'\xff\x00')
                self.assertEqual(checker.main(), 1)
                self.assertIn('Non-text artifact', errors.getvalue())

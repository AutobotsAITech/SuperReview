"""Network-free execution and immutable-reader regression coverage."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/superreview/scripts'
sys.path.insert(0, str(SCRIPTS))
import superreview as sr
import review_reader as rr
import review_workflow as rw


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'fixture')
        self.git('config', 'user.email', 'fixture@invalid')
        (self.repo / 'app.py').write_text('allow = False\n')
        self.git('add', 'app.py')
        self.git('commit', '-qm', 'base')
        self.base = self.git('rev-parse', 'HEAD').strip()
        (self.repo / 'app.py').write_text('allow = True\n')
        self.git('add', 'app.py')
        self.git('commit', '-qm', 'change')
        self.plan = sr.create_plan(self.repo, self.base, 'HEAD')
        self.reader = rr.Reader(self.repo, self.plan)
        self.fake = self.root / 'fake-agent'
        self.fake.write_text('#!' + sys.executable + '\n' + r'''
import json,sys
from pathlib import Path
if '--help' in sys.argv:
    print('--ignore-user-config --ephemeral --output-schema --restricted --permission-prompts --json-schema --strict-mcp-config')
    raise SystemExit(0)
if '--version' in sys.argv:
    print('test-agent 1.0')
    raise SystemExit(0)
if 'features' in sys.argv:
    print('mcp_2026_07_28 under development false')
    raise SystemExit(0)
plan=json.loads(Path('plan.json').read_text())
report={'schema_version':1,'plan_id':plan['plan_id'],'method':'single-context',
        'coverage':[{'path':f['path'],'lens':lens,'status':'reviewed','reason':'Read the synthetic implementation.'}
                    for f in plan['files'] for lens in f['lenses']], 'findings':[], 'limitations':[]}
assert sys.stdin.read()
mode=Path(__file__).with_name('mode').read_text()
if mode!='no-read':
    Path('reader-events.jsonl').write_text(json.dumps({'tool':'read_file','ok':True,'budget_exhausted':mode=='budget'})+'\n')
if mode=='exit': raise SystemExit(5)
if mode=='invalid': report['plan_id']='wrong'
if mode=='incomplete': report['coverage'][0]['status']='not-reviewed'
if mode=='no-read-na':
    Path('reader-events.jsonl').write_text('')
    for item in report['coverage']: item['status']='not-applicable'
if mode=='reproduced': report['method']='multi-provider'
if mode=='finding':
    report['findings']=[{'path':'app.py','side':'head','line':1,'symbol':'allow','root_cause':'allow-all',
    'severity':'P1','title':'Guard permits all requests','trigger':'A request reaches the guard.',
    'evidence':'The guard always returns true.','impact':'Unauthorized requests pass.',
    'refutation':'No other check exists in this fixture.','verification':'reasoned','fix':'Restore the guard.'}]
if 'report' in json.loads(Path('schema.json').read_text()).get('properties', {}):
    report={'report':report,'decisions':[]}
if '--output-last-message' in sys.argv:
    Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text(json.dumps(report))
else:
    response={'subtype':'success','is_error':False,'structured_output':report}
    if mode!='no-cost': response['total_cost_usd']=0.25
    print(json.dumps(response))
''')
        self.fake.chmod(0o700)
        (self.root / 'mode').write_text('clean')

    def git(self, *args):
        env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
        return subprocess.check_output(['git', '-C', str(self.repo), *args], env=env,
                                       stderr=subprocess.DEVNULL).decode()

    def execute(self, mode='clean', agent='codex', **kwargs):
        (self.root / 'mode').write_text(mode)
        output = self.root / ('out-' + mode + '-' + agent)
        with mock.patch.object(sr.shutil, 'which', return_value=str(self.fake)), mock.patch('sys.stdout', new_callable=io.StringIO):
            result = sr.execute_review(self.repo, self.base, agent=agent, output=output, **kwargs)
        return result, output

    def test_both_agents_produce_validated_reports_and_run_metadata(self):
        before = self.git('status', '--porcelain')
        for agent in ('codex', 'claude'):
            code, output = self.execute(agent=agent)
            self.assertEqual(code, 0)
            self.assertTrue((output / 'review.md').is_file())
            self.assertEqual(sr.load_json(output / 'run.json')['status'], 'complete')
            if os.name == 'posix':
                self.assertEqual(output.stat().st_mode & 0o777, 0o700)
                self.assertEqual((output / 'agent.stderr').stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.git('status', '--porcelain'), before)

    def test_findings_and_incomplete_coverage_have_distinct_exit_codes(self):
        self.assertEqual(self.execute('finding')[0], 1)
        self.assertEqual(self.execute('incomplete')[0], 3)

    def test_failed_invalid_and_unsupported_claims_never_create_accepted_report(self):
        for mode in ('invalid', 'exit', 'reproduced', 'no-read', 'no-read-na'):
            with self.subTest(mode=mode), self.assertRaises(sr.ReviewError):
                self.execute(mode)
            output = self.root / ('out-' + mode + '-codex')
            self.assertFalse((output / 'report.json').exists())
            self.assertFalse((output / 'review.md').exists())
            self.assertEqual(sr.load_json(output / 'run.json')['status'], 'failed')

    def test_reader_budget_exhaustion_forces_incomplete_result(self):
        code, output = self.execute('budget')
        self.assertEqual(code, 3)
        self.assertIn('budget was exhausted', sr.load_json(output / 'report.json')['limitations'][0])

    def test_batched_execution_resumes_without_rerunning_completed_groups(self):
        (self.repo / 'second.py').write_text('value = 1\n')
        self.git('add', 'second.py')
        self.git('commit', '-qm', 'second file')
        bundle = rw.prepare(self.repo, self.base, output=self.root/'bundle', max_files=1)
        with mock.patch.object(sr.shutil, 'which', return_value=str(self.fake)):
            self.assertEqual(rw.run_groups(bundle, 'claude', max_groups=1), 3)
            self.assertTrue((bundle/'group-0001/attempt-0001/run.json').exists())
            self.assertFalse((bundle/'group-0002/attempt-0001').exists())
            self.assertEqual(rw.run_groups(bundle, 'claude'), 0)
        self.assertFalse((bundle/'group-0001/attempt-0002').exists())
        self.assertEqual(sr.load_json(bundle/'report.json')['method'], 'independent-readers')
        self.assertTrue((bundle/'complete.json').exists())

    def test_batched_reader_budget_is_shared_and_preserved_gaps_cannot_pass(self):
        (self.repo/'second.py').write_text('value = 1\n')
        self.git('add', 'second.py')
        self.git('commit', '-qm', 'second file')
        bundle = rw.prepare(self.repo, self.base, output=self.root/'limited', max_files=1)
        with mock.patch.object(sr.shutil, 'which', return_value=str(self.fake)):
            self.assertEqual(rw.run_groups(bundle, 'claude', max_tool_calls=1), 3)
        self.assertFalse((bundle/'group-0002/attempt-0001').exists())
        self.assertFalse((bundle/'complete.json').exists())

    def test_long_lines_are_readable_without_silent_truncation(self):
        content = '\U0001f600' * 12000 + 'trailing evidence'
        (self.repo/'long.txt').write_text(content)
        self.git('add', 'long.txt')
        self.git('commit', '-qm', 'long line')
        reader = rr.Reader(self.repo, sr.create_plan(self.repo, self.base, 'HEAD'))
        args = {'side':'head', 'path':'long.txt'}
        reconstructed = ''
        while True:
            result = reader.call('read_file', args)
            self.assertLessEqual(len(json.dumps(result).encode()), rr.PAGE_BYTES)
            page = json.loads(result['content'][0]['text'])
            reconstructed += ''.join(row['text'] for row in page['lines'])
            if page['next_line'] is None:
                break
            args.update(start_line=page['next_line'], start_column=page['next_column'])
        self.assertEqual(reconstructed, content)

    def test_batched_dollar_budget_stops_before_another_provider_call(self):
        (self.repo/'second.py').write_text('value = 1\n')
        self.git('add', 'second.py')
        self.git('commit', '-qm', 'second file')
        bundle = rw.prepare(self.repo, self.base, output=self.root/'dollar-cap', max_files=1)
        with mock.patch.object(sr.shutil, 'which', return_value=str(self.fake)):
            self.assertEqual(rw.run_groups(bundle, 'claude', max_budget_usd=0.5), 3)
        self.assertTrue((bundle/'group-0002/attempt-0001/run.json').exists())
        self.assertFalse((bundle/'attempt-0001').exists())
        self.assertFalse((bundle/'complete.json').exists())

    def test_missing_cost_stops_batched_work_under_a_dollar_cap(self):
        (self.root/'mode').write_text('no-cost')
        bundle = rw.prepare(self.repo, self.base, output=self.root/'no-cost')
        with mock.patch.object(sr.shutil, 'which', return_value=str(self.fake)), \
             self.assertRaisesRegex(sr.ReviewError, 'cost'):
            rw.run_groups(bundle, 'claude', max_budget_usd=1)
        self.assertFalse((bundle/'attempt-0001').exists())

    def test_remote_freshness_failure_prevents_accepting_report(self):
        def changed(): raise sr.ReviewError('PR head changed')
        with self.assertRaisesRegex(sr.ReviewError, 'changed'):
            self.execute('remote-changed', freshness_check=changed)
        self.assertFalse((self.root/'out-remote-changed-codex/report.json').exists())

    def test_existing_output_and_unsupported_budget_are_rejected(self):
        self.execute()
        with self.assertRaises(sr.ReviewError):
            self.execute()
        with self.assertRaises(sr.ReviewError):
            self.execute(max_budget_usd=1)

    def test_output_inside_candidate_repo_is_rejected(self):
        with mock.patch.object(sr.shutil, 'which', return_value=str(self.fake)), self.assertRaisesRegex(sr.ReviewError, 'outside'):
            sr.execute_review(self.repo, self.base, output=self.repo/'artifacts')
        self.assertFalse((self.repo/'artifacts').exists())

    def test_moving_head_is_rejected_before_report_is_accepted(self):
        original_run = sr.run_agent
        def advance(*args):
            original_run(*args)
            self.git('commit', '--allow-empty', '-qm', 'concurrent advance')
        with mock.patch.object(sr, 'run_agent', side_effect=advance), self.assertRaisesRegex(sr.ReviewError, 'moved'):
            self.execute()
        self.assertFalse((self.root/'out-clean-codex'/'report.json').exists())

    def test_artifact_failure_and_cancellation_do_not_leave_accepted_reports(self):
        with mock.patch.object(sr, 'render', side_effect=OSError('render failed')), self.assertRaises(OSError):
            self.execute('render-failure')
        self.assertFalse((self.root/'out-render-failure-codex'/'report.json').exists())
        with mock.patch.object(sr, 'run_agent', side_effect=KeyboardInterrupt):
            code, output = self.execute('cancel')
        self.assertEqual(code, 130)
        self.assertEqual(sr.load_json(output/'run.json')['status'], 'cancelled')
        self.assertFalse((output/'report.json').exists())

    def test_empty_change_does_not_invoke_model(self):
        with mock.patch.object(sr.shutil, 'which', return_value=str(self.fake)), mock.patch.object(sr, 'run_agent') as run:
            output = self.root / 'empty'
            self.assertEqual(sr.execute_review(self.repo, 'HEAD', output=output), 0)
            run.assert_not_called()
            self.assertFalse(sr.load_json(output / 'run.json')['agent_invoked'])

    def test_timeout_terminates_cli(self):
        output = self.root / 'timeout'
        output.mkdir()
        prompt = output / 'prompt'
        prompt.write_text('test')
        with self.assertRaisesRegex(sr.ReviewError, 'timed out'):
            sr.run_agent([sys.executable, '-c', 'import time;time.sleep(30)'], output, prompt, 1)

    def test_oversized_agent_output_fails(self):
        output = self.root / 'overflow'
        output.mkdir()
        prompt = output / 'prompt'
        prompt.write_text('test')
        with mock.patch.object(sr, 'LIMIT', 100), self.assertRaisesRegex(sr.ReviewError, 'output exceeds'):
            sr.run_agent([sys.executable, '-c', 'print("x"*101)'], output, prompt, 5)

    def test_adapter_commands_enforce_selected_tools_and_permissions(self):
        _, output = self.execute()
        codex = sr.agent_command('codex', 'codex', output)
        self.assertIn('--ignore-user-config', codex)
        self.assertEqual(codex[codex.index('--sandbox') + 1], 'read-only')
        self.assertIn('shell_tool', codex)
        self.assertIn('approval_policy="never"', codex)
        claude = sr.agent_command('claude', 'claude', output, max_budget_usd=2)
        self.assertEqual(claude[claude.index('--tools') + 1], '')
        self.assertIn('--restricted', claude)
        self.assertIn('--strict-mcp-config', claude)
        self.assertNotIn('--dangerously-skip-permissions', claude)
        self.assertEqual(claude[claude.index('--max-budget-usd') + 1], '2')

    def result(self, name, arguments):
        return json.loads(self.reader.call(name, arguments)['content'][0]['text'])

    def test_reader_uses_pinned_objects_ignoring_dirty_worktree(self):
        (self.repo / 'app.py').write_text('dirty')
        self.assertEqual(self.result('read_file', {'side':'head','path':'app.py'})['lines'][0]['text'], 'allow = True')
        self.assertEqual(self.result('read_file', {'side':'base','path':'app.py'})['lines'][0]['text'], 'allow = False')
        self.assertEqual(self.result('search', {'side':'head','query':'does-not-exist'})['lines'], [])
        self.assertIn('app.py', self.result('list_files', {'side':'head'})['lines'])
        self.assertTrue(any('+allow = True' in line for line in self.result('diff', {'path':'app.py'})['lines']))

    def test_reader_rejects_untracked_files_paths_and_arbitrary_revisions(self):
        (self.repo / 'private.txt').write_text('not committed')
        for args in ({'side':'HEAD','path':'app.py'}, {'side':'head','path':'../private.txt'},
                     {'side':'head','path':'private.txt'}, {'side':'head','path':str(self.repo/'app.py')}):
            with self.subTest(args=args), self.assertRaises(sr.ReviewError):
                self.result('read_file', args)
        with self.assertRaises(sr.ReviewError):
            self.result('shell', {'command':'anything'})

    def test_reader_never_follows_committed_symlinks(self):
        (self.repo / 'link').symlink_to(self.root / 'outside')
        (self.root / 'outside').write_text('not available')
        self.git('add', 'link')
        self.git('commit', '-qm', 'link')
        reader = rr.Reader(self.repo, sr.create_plan(self.repo, self.base, 'HEAD'))
        with self.assertRaises(sr.ReviewError):
            reader.call('read_file', {'side':'head','path':'link'})

    def test_reader_budget_and_pagination_are_explicit(self):
        reader = rr.Reader(self.repo, self.plan, max_calls=1)
        reader.call('list_files', {'side':'head'})
        with self.assertRaisesRegex(sr.ReviewError, 'budget exhausted'):
            reader.call('list_files', {'side':'head'})
        page = self.reader.page(list(range(101)), 0)
        self.assertEqual(len(page['lines']), 100)
        self.assertEqual(page['next_page'], 1)
        self.assertEqual(self.reader.page(list(range(101)), 1)['lines'], [100])

    def test_reader_budget_survives_server_restart(self):
        events = self.root / 'events'
        events.write_text('')
        first = rr.Reader(self.repo, self.plan, max_calls=1, events=events)
        first.call('list_files', {'side':'head'})
        second = rr.Reader(self.repo, self.plan, max_calls=1, events=events)
        with self.assertRaises(sr.ReviewError):
            second.call('list_files', {'side':'head'})
        records = [json.loads(line) for line in events.read_text().splitlines()]
        self.assertTrue(records[1]['budget_exhausted'])

    def test_stdio_protocol_keeps_tool_errors_and_invalid_requests_distinct(self):
        requests = [
            {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25'}},
            {'jsonrpc':'2.0','method':'notifications/initialized'},
            {'jsonrpc':'2.0','id':2,'method':'tools/list'},
            {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'read_file','arguments':{'side':'head','path':'missing'}}},
            {'jsonrpc':'2.0','id':4,'method':'not-a-method'},
        ]
        source = io.BytesIO(('\n'.join(map(json.dumps, requests))+'\n').encode())
        output = io.StringIO()
        rr.serve(self.reader, source, output)
        responses = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(len(responses), 4)
        self.assertEqual(len(responses[1]['result']['tools']), 4)
        self.assertTrue(responses[2]['result']['isError'])
        self.assertEqual(responses[3]['error']['code'], -32601)

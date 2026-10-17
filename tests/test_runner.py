"""Regression checks for the new launcher's actual failure/safety boundaries."""
import importlib.util,io,json,os,subprocess,sys,tempfile,unittest
from contextlib import redirect_stdout,redirect_stderr
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('runner',ROOT/'training/scripts/run_formal.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
class RunnerTests(unittest.TestCase):
 def test_all_12_configs_are_frozen_and_fresh(self):
  for c in ['C','S','J','SJ']:
   for s in [3407,3408,3409]:
    _,out,e=runner.plan(c,s,'train');_,other,_=runner.plan(c,s,'train')
    self.assertNotEqual(out,other);self.assertFalse(out.exists());self.assertEqual(e['AUTO_RESUME'],'0');self.assertEqual(e['MAX_STEPS'],'500');self.assertEqual(e['TRAIN_TASK_END'],'50');self.assertEqual(e['HOLDOUT_TASK_START'],'50')
    self.assertEqual(float(e['REWARD_STYLE_WEIGHT']),int(c in ['S','SJ']));self.assertEqual(float(e['REWARD_AI_JUDGE_WEIGHT']),int(c in ['J','SJ']))
 def test_dry_run_never_starts_process_or_makes_output(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'new'
   with patch.object(runner.subprocess,'run',side_effect=AssertionError('must not execute')):
    self.assertEqual(runner.main(['--condition','SJ','--seed','3407','--stage','train','--output-root',str(out),'--dry-run']),0)
   self.assertFalse(out.exists())
 def test_rejects_repository_output_path(self):
  with self.assertRaises(ValueError):runner.plan('C',3407,'train',str(ROOT/'data'))
 def test_existing_output_is_never_reused(self):
  with tempfile.TemporaryDirectory() as d,patch.object(runner.subprocess,'run',side_effect=AssertionError('must not execute')):
   with self.assertRaises(FileExistsError):runner.main(['--condition','C','--seed','3407','--stage','train','--output-root',d,'--execute'])
 def test_lora_evaluation_requires_adapter(self):
  with self.assertRaises(SystemExit):runner.main(['--condition','C','--seed','3407','--stage','eval-holdout','--dry-run'])
 def test_judge_execution_requires_endpoint(self):
  with patch.dict(os.environ,{'AI_JUDGE_BASE_URL':''}):
   with self.assertRaises(SystemExit):runner.main(['--condition','J','--seed','3407','--stage','train','--execute'])
 def test_judge_auth_reaches_child_without_entering_plans_or_output(self):
  synthetic='synthetic-auth-for-mocked-child'
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'new';stdout=io.StringIO();stderr=io.StringIO()
   ambient={'AI_JUDGE_API_KEY':synthetic,'AI_JUDGE_BASE_URL':'https://example.invalid/v1','AI_JUDGE_MODEL':'unrelated-model','AI_JUDGE_UNRECOGNIZED':'unrelated-option'}
   with patch.dict(os.environ,ambient),patch.object(runner.subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as child,redirect_stdout(stdout),redirect_stderr(stderr):
    _,_,configuration=runner.plan('J',3407,'train',str(out))
    self.assertNotIn('AI_JUDGE_API_KEY',configuration)
    self.assertEqual(runner.main(['--condition','J','--seed','3407','--stage','train','--output-root',str(out),'--execute']),0)
   child.assert_called_once();env=child.call_args.kwargs['env']
   self.assertEqual(env.get('AI_JUDGE_API_KEY'),synthetic)
   self.assertEqual(env['AI_JUDGE_MODEL'],'qwen-32b')
   self.assertNotIn('AI_JUDGE_UNRECOGNIZED',env)
   saved=(out/'execution-plan.json').read_text()
   for text in [stdout.getvalue(),stderr.getvalue(),saved]:
    self.assertNotIn(synthetic,text);self.assertNotIn('AI_JUDGE_API_KEY',text)
 def test_dry_run_never_exposes_caller_auth(self):
  synthetic='synthetic-auth-for-dry-run';stdout=io.StringIO()
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'new'
   with patch.dict(os.environ,{'AI_JUDGE_API_KEY':synthetic}),patch.object(runner.subprocess,'run',side_effect=AssertionError('must not execute')),redirect_stdout(stdout):
    self.assertEqual(runner.main(['--condition','J','--seed','3407','--stage','train','--output-root',str(out),'--dry-run']),0)
   self.assertFalse(out.exists());self.assertNotIn(synthetic,stdout.getvalue());self.assertNotIn('AI_JUDGE_API_KEY',stdout.getvalue())
if __name__=='__main__':unittest.main()

"""New safe convenience runner. Not a claim to exact historical orchestration."""
from pathlib import Path
import argparse,json,os,subprocess,sys,uuid
ROOT=Path(__file__).resolve().parents[2]
STAGES={'base-train':'eval_base','base-holdout':'eval_base_holdout','train':'train','eval-train':'eval_lora','eval-holdout':'eval_lora_holdout'}
def plan(condition,seed,stage,root=None,adapter=None):
 records=json.loads((ROOT/'training/configs/formal_matrix.json').read_text())
 run=next(r for r in records if r['condition']==condition and r['seed']==seed)
 output=(Path(root) if root else ROOT/'runs'/f'{condition}-{seed}-{stage}-{uuid.uuid4().hex[:12]}').resolve()
 if output==ROOT or ROOT in output.parents and output.parts[len(ROOT.parts)] not in ['runs']:
  raise ValueError('Output must be under runs/ or outside the repository')
 env=run['configuration'].copy();env.update(TEST_MODE=STAGES[stage],AUTO_RESUME='0',RESUME_FROM_CHECKPOINT='none',RUN_ROOT=str(output),RUN_ID=f'{condition}-{seed}',RUN_NAME=condition,LOG_DIR=str(output/'logs'),OUTPUT_DIR=str(output/'trainer'),LORA_OUTPUT_DIR=str(output/'adapter'),LORA_PATH=str(Path(adapter).resolve()) if adapter else str(output/'adapter'),SAVE_BEFORE_AFTER_CSV='0',AI_JUDGE_MODEL='qwen-32b',AI_JUDGE_BASE_URL=os.environ.get('AI_JUDGE_BASE_URL',''),AI_JUDGE_SEED='3407')
 return run,output,env
def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--condition',choices=['C','S','J','SJ'],required=True);p.add_argument('--seed',type=int,choices=[3407,3408,3409],required=True);p.add_argument('--stage',choices=STAGES,required=True);p.add_argument('--output-root');p.add_argument('--adapter');p.add_argument('--dry-run',action='store_true');p.add_argument('--execute',action='store_true');a=p.parse_args(argv)
 if a.dry_run and a.execute:p.error('Choose --dry-run or --execute')
 if not a.execute:a.dry_run=True
 if a.stage.startswith('eval-') and not a.adapter:p.error('LoRA evaluation requires --adapter from a completed train stage')
 run,output,env=plan(a.condition,a.seed,a.stage,a.output_root,a.adapter)
 trainer=ROOT/'training/historical'/run['trainer']/'train.py'
 print(json.dumps({'mode':'DRY RUN' if a.dry_run else 'EXECUTE','historical_run':run['run'],'condition':a.condition,'seed':a.seed,'stage':a.stage,'trainer':str(trainer.relative_to(ROOT)),'configuration':{k:v for k,v in env.items() if k!='AI_JUDGE_BASE_URL'},'judge_endpoint_set':bool(env['AI_JUDGE_BASE_URL']),'limits':'Reconstructed environment. No original adapter/model revision guarantees.'},indent=2))
 if a.dry_run:return 0
 if a.condition in ['J','SJ'] and not env['AI_JUDGE_BASE_URL']:p.error('Set AI_JUDGE_BASE_URL to an authorized OpenAI-compatible Judge service')
 if a.adapter and not (Path(a.adapter)/'adapter_config.json').is_file():p.error('Adapter directory must contain adapter_config.json')
 output.mkdir(parents=True,exist_ok=False)
 (output/'execution-plan.json').write_text(json.dumps({'run':run,'stage':a.stage,'env':{k:v for k,v in env.items() if k!='AI_JUDGE_BASE_URL'}},indent=2)+'\n')
 # Prevent ambient reward/training variables and an unrelated .env from changing this run.
 child={k:v for k,v in os.environ.items() if not k.startswith(('AI_JUDGE_','REWARD_','PERFORMANCE_','TRAIN_TASK_','HOLDOUT_TASK_','LORA_'))}
 child.update(env)
 # Authentication is runtime-only: never add it to the printed/persisted plan.
 if 'AI_JUDGE_API_KEY' in os.environ:child['AI_JUDGE_API_KEY']=os.environ['AI_JUDGE_API_KEY']
 return subprocess.run([sys.executable,str(trainer)],cwd=output,env=child).returncode
if __name__=='__main__':raise SystemExit(main())

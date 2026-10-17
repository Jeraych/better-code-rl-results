"""Recompute cached-timeout and Judge group diagnostics, without API access."""
from collections import Counter,defaultdict
from common import rows,load,matrix,runpath
def reproduce():
 results=[];service=defaultdict(Counter)
 for run in matrix():
  base=runpath(run);tr=rows(base+'/training.csv');groups=defaultdict(list)
  for r in tr:groups[r['step']].append(r)
  timeouts=[r for r in tr if r['test_status']=='timeout']
  d={'run':run['run'],'timeout_rows':len(timeouts),'unique_timeout_task_raw_completion_pairs':len({(r['task_id'],r['raw_completion']) for r in timeouts}),'timeout_tasks':dict(Counter(r['task_id'] for r in timeouts)),'timeout_groups':len({r['step'] for r in timeouts}),'measured_eligible_varying_groups':sum(len({float(r['ai_judge_score']) for r in g if r['ai_judge_status']=='ok'})>1 for g in groups.values()),'effective_judge_varying_groups':sum(len({float(r['reward_ai_judge']) for r in g})>1 for g in groups.values()),'total_reward_varying_groups':sum(len({float(r['reward_total']) for r in g})>1 for g in groups.values())}
  if run['run']==35:
   assert (d['timeout_rows'],d['unique_timeout_task_raw_completion_pairs'],d['timeout_groups'])==(70,27,21)
   assert d['timeout_tasks']=={'HumanEval/15':40,'HumanEval/39':29,'HumanEval/25':1}
  if run['condition'] in ['J','SJ']:
   summary=load(base+'/judge-summary.json');status=summary['statuses']
   assert status['attempt']==status['ok'] and not summary['errors_by_kind']
   service[run['condition']].update(status);d['service_statuses']=status
   assert all(r['ai_judge_status']=='ok' for r in tr if r['test_status']=='passed')
  results.append(d)
 assert service['J']['ok']==2695 and service['SJ']['ok']==2425
 out={'status':'PASS','runs':results,'services':dict(service),'limits':['Cached timeout reuse follows the preserved DIAGNOSTIC_CACHE implementation; the original host/deadline cause is unresolved.','27 distinct task/completion keys are 70 recorded reward-affecting rows, not 70 independent failures.','Service success and schema validity do not validate Judge findings.','Complete transport JSONL is not available for all runs; summaries remain source records.']}
 return out
if __name__=='__main__':
 import json
 print(json.dumps(reproduce(),indent=2))

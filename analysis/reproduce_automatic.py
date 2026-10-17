"""CPU/stdlib recomputation of every saved formal output and reward component."""
from collections import Counter,defaultdict
from common import ROOT,load,rows,sha,matrix,runpath
EXPECTED={'C':[545,394,358],'S':[526,565,495],'J':[542,454,410],'SJ':[527,568,495]}
def reproduce():
 aggregates=defaultdict(Counter);results=[];total_train=0
 frozen=load('manifests/frozen-inputs.json')
 for run in matrix():
  base=runpath(run);ev=rows(base+'/holdout.csv');tr=rows(base+'/training.csv')
  for kind in ['holdout','training']:
   data=(ROOT/base/(kind+'.csv')).read_bytes()
   assert sha(data)==frozen[str(run['run'])][kind],(run['run'],kind,'frozen hash mismatch')
  assert len(ev)==200 and len(tr)==2000,run['run']
  assert len({(r['task_id'],r['generation_idx']) for r in ev})==200
  assert Counter(r['task_id'] for r in ev)=={f'HumanEval/{i}':4 for i in range(50,100)}
  assert {int(r['generation_idx']) for r in ev}==set(range(4))
  assert all(0<=int(r['task_id'].split('/')[1])<50 for r in tr)
  groups=defaultdict(list)
  for r in tr:groups[int(r['step'])].append(r)
  assert len(groups)==500 and all(len(g)==4 for g in groups.values())
  assert all(len({r['completion_index'] for r in g})==4 and len({r['task_id'] for r in g})==1 for g in groups.values())
  assert len({(r['step'],r['completion_index']) for r in tr})==2000
  weights={'reward_format':.1,'reward_syntax':.1,'reward_compile':.3,'reward_tests':4.5,'reward_style':int(run['condition'] in ['S','SJ']),'reward_ai_judge':int(run['condition'] in ['J','SJ']),'reward_performance':0}
  for r in tr:
   computed=sum(w*float(r[k]) for k,w in weights.items())
   assert abs(computed-float(r['reward_total']))<1e-7,(run['run'],r['step'],'reward arithmetic')
   if weights['reward_ai_judge'] and r['test_status']!='passed':assert float(r['reward_ai_judge'])==0
  conf=run['configuration']
  assert conf['AUTO_RESUME']=='0' and conf['MAX_STEPS']=='500' and conf['NUM_GENERATIONS']=='4'
  assert [int(conf[k]) for k in ['TRAIN_TASK_START','TRAIN_TASK_END','HOLDOUT_TASK_START','HOLDOUT_TASK_END']]==[0,50,50,100]
  assert int(conf['SEED'])==run['seed']
  if run['run']>=36:
   meta=load(base+'/metadata.json');assert meta['seed']==run['seed'] and meta['status']=='completed'
   assert meta['configuration']==conf
   assert meta['source_hashes']['train.py']=='edb8384bc6812850e623edba14a8ae18272e3f804458abbc0f67108775ceddcc'
   assert load(base+'/health.json')['pass'] is True
  counts=Counter(n=len(ev),correct=sum(r['test_status']=='passed' for r in ev),clean=sum(r['style_status']=='ok' for r in ev),both=sum(r['test_status']=='passed' and r['style_status']=='ok' for r in ev))
  aggregates[run['condition']].update(counts);total_train+=len(tr)
  results.append({'run':run['run'],'condition':run['condition'],'seed':run['seed'],**counts,'training_rows':len(tr),'groups':len(groups)})
 for c,expected in EXPECTED.items():assert [aggregates[c][k] for k in ['correct','clean','both']]==expected
 assert sum(a['n'] for a in aggregates.values())==2400 and total_train==24000
 for seed in [3407,3408,3409]:
  base=rows(f'data/base/seed-{seed}/holdout.csv');assert len(base)==200
  assert len({(r['task_id'],r['generation_idx']) for r in base})==200
 result={'status':'PASS','heldout_rows':2400,'training_rows':total_train,'base_rows':600,'runs':results,'aggregates':dict(aggregates),'interpretation':'Descriptive output rates. Four outputs per task, three seeds; not independent task trials or pass@k. Saved statuses are not re-executed tests.'}
 return result
if __name__=='__main__':
 import json
 print(json.dumps(reproduce(),indent=2))

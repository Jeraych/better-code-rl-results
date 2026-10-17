"""Recompute orientation, eligibility, frozen assignments, overlaps and preferences."""
from collections import Counter,defaultdict
from common import ROOT,load,sha,rows,matrix,runpath
EXPECTED={'B-C':[14,10,14],'C-S':[16,5,17],'C-J':[20,3,14],'S-SJ':[9,16,12]}
def reproduce():
 data=load('data/human-validation/formal-anonymized.json');records=data['formal'];pairs=defaultdict(list);counts=defaultdict(Counter);phases=defaultdict(lambda:defaultdict(Counter));ruff_tied=directional_tied=0
 assert data['revision']==313
 frozen={}
 for c in ['B','C','S','J','SJ']:
  obj=load(f'data/human-validation/source/outputs-{c}.json')
  outputs=obj if isinstance(obj,list) else obj['outputs']
  frozen.update({o['outputId']:o for o in outputs})
 sources={}
 for run in matrix():
  path=runpath(run)+'/holdout.csv';sources[(run['condition'],run['seed'])]=(rows(path),sha((ROOT/path).read_bytes()))
 for seed in [3407,3408,3409]:
  path=f'data/base/seed-{seed}/holdout.csv';sources[('B',seed)]=(rows(path),sha((ROOT/path).read_bytes()))
 for out in frozen.values():
  source,sourcehash=sources[(out['condition'],out['seed'])];r=source[out['sourceRow']-2]
  assert out['sourceHash']==sourcehash and (out['taskId'],out['ordinal'])==(r['task_id'],int(r['generation_idx']))
  assert out['code']==r['extracted_code'] and out['rawHash']==sha(r['raw_completion'].encode())
 catalog={r['pairId']:r for r in load('data/human-validation/source/catalog.json')['pairs']}
 schedule={'joint':data['joint'],**data['assignments']}
 scheduled={(who,a['pairId']):(a['a'],a['b']) for who,assignments in schedule.items() for a in assignments}
 for row in records:
  a,b=row['aOutput'],row['bOutput'];choice=row['choice'];canonical='Equal' if choice=='Equal' else row[choice.lower()+'Output']['condition']
  assert canonical==row['canonicalPreference'] and a['testStatus']==b['testStatus']=='passed'
  assert a['code']!=b['code'] and a['taskId']==b['taskId']==row['taskId']
  assert (a['seed'],a['ordinal'])==(b['seed'],b['ordinal'])
  assert row['eligibility']['eligible'] and row['eligibility']['bothCorrect'] and not row['eligibility']['exactCodeMatch']
  assert catalog[row['pairId']]==row['eligibility']
  assert scheduled[(row['reviewer'],row['pairId'])]==(row['a'],row['b'])
  assert (row['a'],row['b'])==(a['outputId'],b['outputId'])
  for out in [a,b]:
   original=frozen[out['outputId']]
   for k,v in out.items():assert original[k]==v,(out['outputId'],k)
   assert sha(out['code'].encode())==out['codeHash']
  pairs[row['pairId']].append(row);counts[row['contrast']][canonical]+=1;phases[row['contrast']][row['reviewer']][canonical]+=1
  if a['ruffScore']==b['ruffScore']:ruff_tied+=1;directional_tied+=canonical!='Equal'
 assert len(records)==150 and len(pairs)==140 and len({r['taskId'] for r in records})==47
 assert len(scheduled)==150 and all(len(v) in [1,2] for v in pairs.values())
 contrasts={}
 for c,expected in EXPECTED.items():
  categories=[c.split('-')[0],'Equal',c.split('-')[1]];actual=[counts[c][k] for k in categories];assert actual==expected
  contrasts[c]={'categories':categories,'counts':actual,'phases':{p:[co[k] for k in categories] for p,co in phases[c].items()}}
 overlaps=[(p,rs) for p,rs in pairs.items() if len(rs)==2];assert {p for p,_ in overlaps}==set(data['overlap'])
 m=[[0]*3 for _ in range(3)]
 for p,rs in overlaps:
  who={r['reviewer']:r for r in rs};assert set(who)=={'reviewer_1','reviewer_2'}
  c=rs[0]['contrast'].split('-');categories=[c[0],'Equal',c[1]]
  m[categories.index(who['reviewer_1']['canonicalPreference'])][categories.index(who['reviewer_2']['canonicalPreference'])]+=1
 observed=sum(m[i][i] for i in range(3))/10;chance=sum(sum(m[i])*sum(row[i] for row in m) for i in range(3))/100;kappa=(observed-chance)/(1-chance)
 assert len(overlaps)==10 and observed==.5 and abs(kappa-.2537313432835821)<1e-12
 assert (ruff_tied,directional_tied)==(108,77)
 weighted=defaultdict(Counter);paircounts=Counter();bycontrast=defaultdict(lambda:Counter(n=0,agree=0))
 for pair,rs in pairs.items():
  paircounts[rs[0]['contrast']]+=1
  for r in rs:weighted[r['contrast']][r['canonicalPreference']]+=1/len(rs)
  if len(rs)==2:
   c=rs[0]['contrast'];bycontrast[c]['n']+=1;bycontrast[c]['agree']+=rs[0]['canonicalPreference']==rs[1]['canonicalPreference']
 out={'status':'PASS','responses':150,'unique_pairs':140,'task_identities':47,'missing_task_identities':[f'HumanEval/{n}' for n in range(50,100) if f'HumanEval/{n}' not in {r['taskId'] for r in records}],'contrasts':contrasts,'distinct_pairs_per_contrast':dict(paircounts),'equal_pair_weight_sensitivity':{c:{'categories':contrasts[c]['categories'],'counts':[weighted[c][k] for k in contrasts[c]['categories']]} for c in contrasts},'overlap':{'n':10,'agreement':observed,'matrix':m,'kappa':kappa,'per_contrast':dict(bycontrast)},'ruff_score_ties':ruff_tied,'directional_preferences_with_tied_ruff':directional_tied,'limits':'Two project authors, 50 joint responses and 100 independent responses. Conditional on both-correct, non-identical outputs. Pseudonymous records remain linkable; the user confirmed both authors agree to this private results snapshot on 17 October 2026.'}
 return out
if __name__=='__main__':
 import json
 print(json.dumps(reproduce(),indent=2))

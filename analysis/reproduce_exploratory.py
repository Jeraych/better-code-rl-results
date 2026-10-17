"""Recompute pivotal performance/prompt calibration screens from saved rows."""
from common import rows
from collections import defaultdict,Counter
import statistics
def reproduce():
 run=rows('exploratory/run-12/samples.csv');eligible=[r for r in run if r['performance_status']=='ok'];groups=defaultdict(list)
 for r in run:groups[r['step']].append(r)
 perf={'rows':len(run),'eligible':len(eligible),'mean_eligible_score':statistics.mean(float(r['performance_score']) for r in eligible),'eligible_at_max':sum(float(r['performance_score'])==1 for r in eligible),'groups':len(groups),'zero_total_reward_variation_groups':sum(len({float(r['reward_total']) for r in g})==1 for g in groups.values())}
 assert (perf['rows'],perf['eligible'],perf['eligible_at_max'],perf['groups'],perf['zero_total_reward_variation_groups'])==(1000,960,779,500,408)
 calibration=rows('exploratory/prompt-ab/per_candidate.csv');by=defaultdict(list)
 for r in calibration:by[r['instrument']].append(r)
 assert len(calibration)==160 and len(by)==2;summary={}
 for instrument,records in by.items():
  gs=defaultdict(list)
  for r in records:gs[r['group_id']].append(float(r['score']))
  assert len(records)==80 and len(gs)==20 and all(len(g)==4 for g in gs.values())
  assert all(r['status']=='ok' and r['finish_reason']=='stop' for r in records)
  summary[instrument]={'reviews':80,'groups':20,'equal_score_groups':sum(len(set(g))==1 for g in gs.values()),'mean_within_group_population_sd':statistics.mean(statistics.pstdev(g) for g in gs.values()),'mean_score':statistics.mean(float(r['score']) for r in records)}
 assert sorted(x['equal_score_groups'] for x in summary.values())==[11,18]
 return {'status':'PASS','run12':perf,'prompt_calibration':summary,'limits':'Saved exploratory records only; prepared 144-call plan is not classified as completed. No API calls, candidate execution or training.'}
if __name__=='__main__':
 import json
 print(json.dumps(reproduce(),indent=2))

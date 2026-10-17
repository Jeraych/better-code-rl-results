"""Regenerate report figures and their plotted data from freshly recomputed rows."""
from common import ROOT,save
from reproduce_automatic import reproduce as automatic
from reproduce_human import reproduce as human
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
import numpy as np
def main():
 a,h=automatic(),human();out=ROOT/'figures';out.mkdir(exist_ok=True)
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'savefig.dpi':200})
 def savefig(fig,name):
  for ext in ['png','svg','pdf']:fig.savefig(out/f'{name}.{ext}',bbox_inches='tight',pad_inches=.12)
  plt.close(fig)
 fig,ax=plt.subplots(figsize=(12,3.3));ax.axis('off');ax.set_xlim(0,12);ax.set_ylim(0,3)
 boxes=[(.1,.9,2.3,1.2,'Reward screening\nPilots + negative findings'),(3.1,.5,2.6,2,'C / S / J / SJ\n3 seeds × 500 steps\nTrain tasks 0–49'),(6.4,.9,2.3,1.2,'Saved held-out outputs\nTasks 50–99\n2,400 outputs'),(9.3,.9,2.5,1.2,'Blinded author review\n140 pairs / 150 ratings\nTwo project authors')]
 for x,y,w,hh,txt in boxes:
  ax.add_patch(FancyBboxPatch((x,y),w,hh,boxstyle='round,pad=.04',fc='white',ec='black'));ax.text(x+w/2,y+hh/2,txt,ha='center',va='center',fontsize=9)
 for x1,x2 in [(2.45,3.02),(5.75,6.32),(8.75,9.22)]:ax.add_patch(FancyArrowPatch((x1,1.5),(x2,1.5),arrowstyle='-|>',mutation_scale=12))
 savefig(fig,'figure1_study_workflow')
 names=['C','S','J','SJ'];keys=['correct','clean','both'];vals=np.array([[a['aggregates'][n][k] for k in keys] for n in names])/600*100
 fig,ax=plt.subplots(figsize=(9.6,4.6));x=np.arange(3);w=.19
 for i,name in enumerate(names):
  bars=ax.bar(x+(i-1.5)*w,vals[i],width=w,label=name)
  for b,v in zip(bars,vals[i]):ax.annotate(f'{v:.1f}',(b.get_x()+b.get_width()/2,v),xytext=(0,3),textcoords='offset points',ha='center',fontsize=8)
 ax.set(ylim=(0,106),ylabel='Held-out outputs (%)',xticks=x,xticklabels=['Correctness','Ruff-clean','Both criteria']);ax.set_yticks(range(0,101,20));ax.legend(ncol=4,loc='upper center',bbox_to_anchor=(.5,1.08),frameon=False);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);fig.tight_layout();savefig(fig,'figure2_automatic_outcomes')
 contrasts=list(h['contrasts']);raw=np.array([h['contrasts'][c]['counts'] for c in contrasts]);values=raw/raw.sum(axis=1,keepdims=True)*100
 fig,ax=plt.subplots(figsize=(9.6,4.6));left=np.zeros(4)
 for j,(label,color) in enumerate(zip(['First condition','Equal','Second condition'],['#356b96','#c1c5ca','#b96330'])):
  ax.barh(contrasts,values[:,j],left=left,label=label,color=color)
  for i,v in enumerate(values[:,j]):ax.text(left[i]+v/2,i,f'{raw[i,j]}',ha='center',va='center',color='white' if j!=1 else 'black',weight='bold')
  left+=values[:,j]
 ax.set(xlim=(0,100),xlabel='Formal judgments within contrast (%)');ax.invert_yaxis();ax.legend(ncol=3,loc='upper center',bbox_to_anchor=(.5,1.15),frameon=False);fig.tight_layout();savefig(fig,'figure3_human_preferences')
 save('figures/figure-data.json',{'automatic_counts':{n:[a['aggregates'][n][k] for k in keys] for n in names},'human_counts':{c:h['contrasts'][c]['counts'] for c in contrasts},'denominators':{'automatic_per_condition':600,'human':{c:sum(h['contrasts'][c]['counts']) for c in contrasts}}})
 print('PASS: 3 figures regenerated in PNG, SVG and PDF; figure-data.json comes from saved rows.')
if __name__=='__main__':main()

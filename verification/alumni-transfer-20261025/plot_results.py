"""Plot archived model sensitivity summaries; no claims of physical validity."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parent
settings=[('friction-02',.2),('primary',.35),('friction-05',.5)]
data=[json.loads((root/name/'summary.json').read_text()) for name,_ in settings]
fig,axes=plt.subplots(1,3,figsize=(12,3.7),layout='constrained')
for team,color in [('baseline','#D97830'),('candidate','#167680')]:
    series=[d['team_totals'][team] for d in data]
    values=[
        [100*s['defending_support_behind_fraction'] for s in series],
        [100*s['danger_ball_fraction'] for s in series],
        [100*s['disc_overlap_player_seconds']/s['playing_player_seconds'] for s in series]]
    for ax,v in zip(axes,values):
        ax.plot([x for _,x in settings],v,'o-',color=color,label=team)
for ax,title in zip(axes,['Support behind ball while defending (%)',
                          'Ball in own danger area (%)',
                          'Disc overlap exposure per player-time (%)']):
    ax.set_title(title,fontsize=10)
    ax.set_xlabel('Assumed ball deceleration (m/s²)')
    ax.grid(alpha=.2)
axes[0].legend(frameon=False)
fig.suptitle('20 paired games per setting: model sensitivity, not hardware performance',fontsize=12)
fig.savefig(root/'model-sensitivity.png',dpi=170)
plt.close(fig)

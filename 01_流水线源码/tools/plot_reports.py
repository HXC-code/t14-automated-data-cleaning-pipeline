"""Real independent outcomes only; every fixed seed is retained."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from src.paths import FINAL,save
sys.path.insert(0,str(FINAL/'tools/figure_qa'))
from audit_panel_alignment import require_matplotlib_panel_alignment

plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':9,'axes.spines.top':False,'axes.spines.right':False,
                     'axes.linewidth':.8,'legend.frameon':False,'pdf.fonttype':42,'svg.fonttype':'none'})


def export(fig,name):
    fig.canvas.draw();base=FINAL/'figures'/name
    require_matplotlib_panel_alignment(fig,json_out=str(base)+'.alignment.json',overlay_svg=str(base)+'.alignment.svg',strict=True)
    fig.savefig(str(base)+'.pdf');fig.savefig(str(base)+'.svg');fig.savefig(str(base)+'.png',dpi=300);fig.savefig(str(base)+'.tiff',dpi=600,pil_kwargs={'compression':'tiff_lzw'})
    plt.close(fig)


def main():
    save(FINAL/'figures/figure_contract.json',dict(conclusion='The frozen J candidate fails the 10% independent F1 target; quality and engineering success do not replace it.',
         backend='Python matplotlib',archetype='single-panel quantitative figures',
         evidence=['All 15 paired F1 gains, five fixed seeds per rate','Observed before/after rule counts in the prespecified middle-noise population','Strict restoration for all eight injection types and all noise levels'],
         n='5 disjoint groups x1600; 8000 unique records reused across three noise conditions',
         uncertainty='sample SD ddof=1 for F1; quality charts show exact pooled counts/proportions, no uncertainty inference',
         exclusions='none in F1/type chart; before/after chart explicitly focuses on 10%, all rates tabulated',
         formats=['PDF','SVG','300dpi PNG','600dpi TIFF'],minimum_font_pt=8,source_files=['reports/五次独立实验结果.csv','reports/修复前后质量统计.csv','reports/各错误类型修复统计.csv']))
    d=pd.read_csv(FINAL/'reports/五次独立实验结果.csv')
    fig,ax=plt.subplots(figsize=(7.2,4.7));fig.subplots_adjust(left=.12,right=.96,bottom=.20,top=.84)
    for i,rate in enumerate([.03,.1,.2]):
        values=d[d.rate==rate].sort_values('seed').gain_pp.to_numpy();assert len(values)==5
        color='#B07934' if rate==.1 else '#548779';mean=values.mean();sd=values.std(ddof=1)
        ax.scatter(i+np.linspace(-.08,.08,5),values,s=26,color=color,alpha=.6,zorder=3)
        ax.errorbar([i],[mean],yerr=[sd],fmt='D',color=color,markersize=6,capsize=5,elinewidth=1.3,label='Mean ± Sample SD' if i==0 else None,zorder=4)
        ax.text(i,max(values.max(),mean+sd)+.25,f'{mean:.4f} pp',ha='center',color=color,fontsize=9)
    ax.axhline(3,color='#666666',lw=.9,ls='--',label='3 pp Requirement');ax.set(xlim=(-.55,2.55),ylim=(0,7),xticks=[0,1,2],xticklabels=['3% noise','10% noise','20% noise'],ylabel='Independent F1 gain, J minus raw (pp)')
    ax.grid(False);ax.legend(loc='lower center',bbox_to_anchor=(.5,1.03),ncol=2)
    fig.text(.12,.055,'5 fixed seeds; all paired gains shown. Middle-noise mean is below 3 pp.',fontsize=8)
    export(fig,'下游F1独立验收图')
    q=pd.read_csv(FINAL/'reports/修复前后质量统计.csv');q=q[q.rate==.1].groupby('state').sum(numeric_only=True)
    columns=['missing_cells','numeric_type_range_alerts','spelling_alerts','format_alerts','unit_conversion_proposals','cross_field_alert_cells','detected_alert_cells']
    labels=['Missing','Numeric\nalerts','Spelling','Format','Unit\nproposals','Cross-field\nalerts','All\nalerts']
    fig,ax=plt.subplots(figsize=(8,4.9));fig.subplots_adjust(left=.12,right=.97,bottom=.23,top=.82)
    for offset,state,color,label in [(-.24,'original','#AEB7BA','Original, native missing'),(0,'dirty','#86A6B5','Injected dirty'),(.24,'J','#548779','J repaired')]:
        ax.bar(np.arange(len(columns))+offset,[q.loc[state,c] for c in columns],width=.22,color=color,label=label)
    ax.set(xticks=np.arange(len(columns)),xticklabels=labels,ylabel='Cells / proposals, pooled count',ylim=(0,float(q[columns].to_numpy().max())*1.12))
    ax.grid(axis='y',color='#E7E7E7',lw=.6);ax.set_axisbelow(True);ax.legend(loc='lower center',bbox_to_anchor=(.5,1.03),ncol=3,columnspacing=1.2)
    fig.text(.12,.06,'10% noise; 8,000 rows. Rule alerts may overlap and are not ground-truth errors.',fontsize=8)
    export(fig,'中噪声修复前后质量对比图')
    t=pd.read_csv(FINAL/'reports/各错误类型修复统计.csv').groupby(['rate','type'])[['injected','strict_restored']].sum()
    types=['missing','range','outlier','unit','typo','format','fd','logic'];names=['Missing','Overwrite','Outlier','Unit conversion','Spelling','Format','Education FD','Semantic logic']
    fig,ax=plt.subplots(figsize=(7.2,5.0));fig.subplots_adjust(left=.23,right=.96,bottom=.20,top=.83)
    for rate,offset,color,marker in [(.03,-.2,'#52778A','o'),(.1,0,'#B07934','s'),(.2,.2,'#548779','^')]:
        values=[100*t.loc[(rate,k),'strict_restored']/t.loc[(rate,k),'injected'] for k in types]
        ax.scatter(values,np.arange(8)+offset,s=30,color=color,marker=marker,label=f'{rate:.0%} Noise')
    ax.set(yticks=np.arange(8),yticklabels=names,xlim=(-2,104),xlabel='Strict restoration of injected cells (%)');ax.invert_yaxis()
    ax.grid(axis='x',color='#E7E7E7',lw=.6);ax.set_axisbelow(True);ax.legend(loc='lower center',bbox_to_anchor=(.5,1.03),ncol=3)
    fig.text(.12,.055,'Exact pooled proportions; plausible imputation is excluded from strict restoration.',fontsize=8)
    export(fig,'各错误类型严格原值还原图')


if __name__=='__main__':main()

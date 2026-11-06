"""V2统一实验入口。原始行去重后随机互斥划分，训练参考冻结，验证阈值。"""
import sys,json,time,random,math,platform,statistics
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parent/'exp'))
import run_exp as R
import pipeline2 as P
import dq_audit as A
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'v2_results';OUT.mkdir(exist_ok=True)
SEEDS=list(range(20260601,20260606)); RATES=[.03,.10,.20]
def save(name,obj):
 (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
def metric(y,s,thr=0):
 tp=sum(a==1 and b>=thr for a,b in zip(y,s));fp=sum(a==0 and b>=thr for a,b in zip(y,s));fn=sum(a==1 and b<thr for a,b in zip(y,s))
 p,r,f=R.prf(tp,fp,fn)
 return dict(accuracy=round(sum((b>=thr)==bool(a) for a,b in zip(y,s))/len(y),4),precision=p,recall=r,f1=f,auc=R.auc(y,s),tp=tp,fp=fp,fn=fn)
def pool_split(raw,seed):
 # 只排除缺失及已知教育编码冲突；不按R3筛选，不用全表统计量。
 seen=set();pool=[]
 for i,r in enumerate(raw):
  k=tuple(r[c] for c in R.COLS)
  if k in seen:continue
  seen.add(k)
  if all(r[c] is not None for c in R.COLS) and R.EDU2NUM.get(r['education'])==r['education_num']:pool.append((i,r))
 random.Random(seed).shuffle(pool)
 return pool[:7000],len(pool)
def features(rows,dom,stats,reference):return P.cell_features(rows,dom,{},stats,R.EDU2NUM,reference=reference)[0]
def cells(rows):return [(i,c) for i in range(len(rows)) for c in R.COLS]
def detector(raw,rate):
 paired,n=pool_split(raw,SEEDS[0]);base=[r for i,r in paired];train=base[:3400];val=base[3400:4400];ev=base[4400:5400]
 dom=R.build_domain(train);dirty,truth,dups=R.inject(base[:5400],dom,rate,SEEDS[0]+int(rate*100));dirty=dirty[:5400]
 ref=dirty[:3400];_,stats=R.stat_scan(ref);X=features(dirty,dom,stats,ref);keys=cells(dirty);y=[int(k in truth) for k in keys]
 Xtr=X[:51000];yv=y[51000:66000];ye=y[66000:81000];Xe=X[66000:81000];ke=keys[66000:81000]
 sub=random.Random(SEEDS[0]).sample(range(len(Xtr)),14000);t=time.perf_counter();gb=P.GBDT(rounds=60,depth=3,lr=.18).fit([Xtr[i] for i in sub],[y[i] for i in sub]);fit=time.perf_counter()-t
 vs=gb.predict(X[51000:66000]);threshold=max(sorted(set(vs)),key=lambda th:metric(yv,vs,th)['f1']) if False else None
 # 195个验证集分位点，禁止使用评估标签调参
 qs=sorted(set(R.pct(vs,k/200) for k in range(4,199)));threshold=max(qs,key=lambda th:metric(yv,vs,th)['f1'])
 t=time.perf_counter();scores=gb.predict(Xe);pred=time.perf_counter()-t
 rh=R.rule_scan(dirty,dom);sh,_=R.stat_scan(dirty,reference=ref);core={k:v for k,v in rh.items() if set(v)&{'R0','R7','R10'}}
 # IF标准化只在训练行拟合；编码不在评估数据上重新拟合
 from sklearn.preprocessing import StandardScaler
 med={c:R.pct([r[c] for r in ref if r[c] is not None],.5) for c in R.NUM}
 numeric=lambda rr:[[r[c] if r[c] is not None else med[c] for c in R.NUM] for r in rr]
 scaler=StandardScaler().fit(numeric(ref));enc=scaler.transform(numeric(dirty)).tolist();t=time.perf_counter();iso=R.IForest(80,256).fit(enc[:3400]);ift=time.perf_counter()-t
 sc=iso.score(enc);ith=R.pct(sc[:3400],.97);ih={}
 for i,s in enumerate(sc):
  if s>ith:
   c=max(R.NUM,key=lambda c:abs((dirty[i][c] if dirty[i][c] is not None else med[c])-stats[c]['median'])/(stats[c]['sigma'] or 1));ih[(i,c)]=s
 det={};binary={}
 for name,hit in [('全规则',rh),('通用规则',core),('统计检测',sh),('孤立森林',ih)]:binary[name]=[float(k in hit) for k in ke]
 binary['单元分类器']=[float(s>=threshold) for s in scores]
 for name,rule in [('通用规则+分类器',core),('全规则+分类器',rh)]:binary[name]=[float(k in rule or s>=threshold) for k,s in zip(ke,scores)]
 for name,bs in binary.items():
  ss=scores if name=='单元分类器' else ([max(1/(1+math.exp(-max(-30,min(30,s)))),float(k in (rh if name=='全规则+分类器' else core))) for k,s in zip(ke,scores)] if '+' in name else bs)
  det[name]=metric(ye,bs,.5);det[name]['auc']=R.auc(ye,ss)
  det[name]['per_type_recall']={typ:round(sum(b for k,b in zip(ke,bs) if truth.get(k)==typ)/max(1,sum(truth.get(k)==typ for k in ke))*100,2) for typ in R.TYPES[:-1]}
 review=[];audit=[];fixed,acts=R.repair(dirty,dom,None,stats,dedup=False,audit=audit,reference=ref,review=review,hits=rh)
 by={};reviews={(a['row'],a['col']) for a in review};rv=Counter()
 for typ in R.TYPES[:-1]:
  kk=[k for k in ke if truth.get(k)==typ];ok=sum(fixed[i][c]==base[i][c] for i,c in kk);by[typ]={'cells':len(kk),'restored':ok,'accuracy':round(ok/max(1,len(kk))*100,2)}
 rest={'typo','format','unit','fd','logic'};ks=[k for k in ke if truth.get(k) in rest];non=[k for k in ke if truth.get(k) in {'range','outlier'}];missing=[k for k in ke if truth.get(k)=='missing']
 imp={};bf=metric(ye,scores,threshold)['f1']
 for j,name in enumerate(P.cell_features([],dom,{},stats,R.EDU2NUM,reference=ref)[1]):
  xp=[x[:] for x in Xe];col=[x[j] for x in xp];random.Random(SEEDS[0]+j).shuffle(col)
  for x,v in zip(xp,col):x[j]=v
  imp[name]=round((bf-metric(ye,gb.predict(xp),threshold)['f1'])*100,3)
 save(f'predictions_{int(rate*100)}.json',{'keys':ke,'truth':ye,'scores':scores,'threshold':threshold,'binary':binary})
 save(f'split_{int(rate*100)}.json',{'raw_row_ids':{'train':[i for i,r in paired[:3400]],'validation':[i for i,r in paired[3400:4400]],'evaluation':[i for i,r in paired[4400:5400]],'downstream_test':[i for i,r in paired[5400:7000]]}})
 return {'target_rate_pct':rate*100,'injected_cells':len(truth),'total_cells':81000,'actual_pct':round(len(truth)/81000*100,4),'by_type':dict(Counter(truth.values())),'duplicates_separate':len(dups),'eval_positives':sum(ye),'eval_cells':len(ye),'clean_pool':n,'detect':det,'threshold':threshold,'repair':{'by_type':by,'restorable_accuracy':round(sum(fixed[i][c]==base[i][c] for i,c in ks)/len(ks)*100,2),'original_restorable_accuracy':round(sum(fixed[i][c]==base[i][c] for i,c in ke if truth.get((i,c)) in rest|{'missing'})/sum(truth.get(k) in rest|{'missing'} for k in ke)*100,2),'missing_fill_rate':round(sum(fixed[i][c] is not None for i,c in missing)/max(1,len(missing))*100,2),'review_rate':round(sum(k in reviews for k in non)/max(1,len(non))*100,2),'all_accuracy':round(sum(fixed[i][c]==base[i][c] for i,c in ke if (i,c) in truth)/sum(ye)*100,2),'actions':dict(acts)},'importance':imp,'timing':{'gb_fit':fit,'gb_predict_15000_cells':pred,'if_fit':ift},'roc':R.roc_curve(ye,scores)}
def downstream(raw):
 out={}
 for rate in RATES:
  reps=[]
  for seed in SEEDS:
   paired,_=pool_split(raw,seed);base=[r for i,r in paired];train=base[:4400];test=base[5400:7000];dom=R.build_domain(train)
   dirty,truth,dup=R.inject(train,dom,rate,seed+int(rate*100));dirty=dirty[:4400]
   fixed,_=R.repair(dirty,dom,None,None,dedup=False,reference=dirty)
   med={c:R.pct([r[c] for r in dirty if r[c] is not None],.5) for c in R.NUM};rec={'seed':seed,'injected_cells':len(truth),'actual_pct':len(truth)/66000*100}
   for name,data in [('干净',train),('未清洗',dirty),('修复后',fixed)]:
    # 同一超参；每个版本的尺度和中位数均在该版本训练数据拟合
    m={c:R.pct([r[c] for r in data if r[c] is not None],.5) for c in R.NUM}
    fn,dim=R.train_lr([(r,int(r['income']=='>50K')) for r in data],m)
    rec[name]=metric([int(r['income']=='>50K') for r in test],fn(test),0)
   rec['gain_f1']=(rec['修复后']['f1']-rec['未清洗']['f1'])*100;rec['gain_auc']=(rec['修复后']['auc']-rec['未清洗']['auc'])*100;reps.append(rec);print('downstream',int(rate*100),seed,rec['gain_f1'],flush=True)
  agg={name:{m:{'mean':statistics.mean(r[name][m] for r in reps),'std':statistics.stdev(r[name][m] for r in reps)} for m in ['accuracy','precision','recall','f1','auc']} for name in ['干净','未清洗','修复后']}
  out[str(int(rate*100))]={'runs':reps,'aggregate':agg,'gain_f1':{'mean':statistics.mean(r['gain_f1'] for r in reps),'std':statistics.stdev(r['gain_f1'] for r in reps)},'gain_auc':{'mean':statistics.mean(r['gain_auc'] for r in reps),'std':statistics.stdev(r['gain_auc'] for r in reps)}};save('downstream.json',out)
 return out
def main():
 t=time.perf_counter();raw=R.load_adult();out={'environment':{'python':sys.version,'platform':platform.platform()},'protocol':{'detector_train':3400,'validation':1000,'evaluation':1000,'downstream_train':4400,'downstream_test':1600,'seed':SEEDS,'threshold_downstream_logit':0,'dedup_before_split':True},'detectors':{}}
 for rate in RATES:
  out['detectors'][str(int(rate*100))]=detector(raw,rate);save('experiments.json',out);print('detector',rate,'done',flush=True)
 out['downstream']=downstream(raw);out['wall_seconds']=time.perf_counter()-t;save('experiments.json',out)
if __name__=='__main__':main()

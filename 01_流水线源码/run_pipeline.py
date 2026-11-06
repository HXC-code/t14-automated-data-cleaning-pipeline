"""One command: ingest -> profile/detect/locate -> frozen J -> review -> export."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import argparse,csv,json,time,uuid
from pathlib import Path
from copy import deepcopy
from src.paths import FINAL,CONFIG,FEATURES,NUM,save,csvsave,sha,now
from src.runtime import FrozenCleaner,verify_candidate,BOUNDS
from src.csvio import read_input,write_features
from src.auditio import enrich,forward,rollback,signature,deduplicate


def manual_decisions(rows,ids,events,path):
    positions={r:i for i,r in enumerate(ids)};resolved=set();modified=0
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        decisions=list(csv.DictReader(f))
    seen=set()
    for d in decisions:
        if d.get('decision','').strip() not in ['keep','approve']:continue
        key=(d['record_id'],d['field']);assert key not in seen,'Duplicate review decision';seen.add(key)
        assert d['record_id'] in positions and d['field'] in FEATURES
        i=positions[d['record_id']];c=d['field'];before=rows[i][c];value=before
        if d['decision'].strip()=='approve':
            v=d.get('new_value','');value=None if v.strip() in ['','?'] else float(v) if c in NUM else v
            if c in NUM and value is not None:assert BOUNDS[c][0]<=value<=BOUNDS[c][1] and value.is_integer()
        events.append(dict(op='cell_fix' if value!=before else 'review',row=i,col=c,before=before,after=value,action='explicit_human_'+d['decision'].strip(),
                           reasons=[d.get('reason','Human decision file')],human_authorized=True))
        rows[i][c]=value;modified+=value!=before;resolved.add((i,c))
    return resolved,modified


def run(input_path,output,seed=20260601,rate=.1,dedup=False,decisions=None):
    verify_candidate();output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    marker=output/'run_started.json'
    with marker.open('x',encoding='utf-8') as f:json.dump(dict(input_sha256=sha(input_path),start_utc=now(),seed=seed,rate=rate),f)
    start=time.perf_counter();ids,observed=read_input(input_path);cleaner=FrozenCleaner(seed,rate)
    before=cleaner.profile(observed);result=cleaner.repair(observed,'J');fixed=deepcopy(result['rows']);events=deepcopy(result['audit'])
    automatic={(i,c) for i in range(len(fixed)) for c in FEATURES if fixed[i][c]!=observed[i][c]}
    resolved=set();human_count=0
    if decisions:resolved,human_count=manual_decisions(fixed,ids,events,decisions)
    after=cleaner.profile(fixed);review=[r for r in result['review'] if (r['row'],r['col']) not in resolved]
    kept_ids=list(ids)
    if dedup:fixed,kept_ids=deduplicate(fixed,events,ids)
    run_id=uuid.uuid4().hex;audit=enrich(events,ids,run_id)
    with (output/'audit.jsonl').open('w',encoding='utf-8') as f:
        for e in audit:f.write(json.dumps(e,ensure_ascii=False)+'\n')
    with (output/'audit.jsonl').open(encoding='utf-8') as f:disk=[json.loads(line) for line in f if line.strip()]
    assert forward(observed,disk)==fixed
    restored=rollback(fixed,disk);assert restored==observed
    write_features(output/'cleaned.csv',kept_ids,fixed);write_features(output/'rolled_back.csv',ids,restored,indicators=False)
    queue=[dict(record_id=ids[r['row']],field=r['col'],observed_value=r['value'],reasons=';'.join(r['reasons']),decision='',new_value='',reason='') for r in review]
    if queue:csvsave(output/'review.csv',queue)
    else:
        (output/'review.csv').write_text('record_id,field,observed_value,reasons,decision,new_value,reason\n',encoding='utf-8')
    locations=[]
    bykey={(r['row'],r['col']):r['reasons'] for r in result['review']}
    byevent={(e['row'],e['col']):[e['action']] for e in result['events']}
    for i,c in sorted(result['flags']):locations.append(dict(record_id=ids[i],field=c,observed_value=observed[i][c],reason=';'.join(bykey.get((i,c),byevent.get((i,c),['frozen_detector_alert']))),
                                                                              result='modified' if (i,c) in automatic else 'review'))
    csvsave(output/'detected_cells.csv',locations)
    elapsed=time.perf_counter()-start
    report=dict(run_id=run_id,candidate='frozen V3.3-J',input_file=str(Path(input_path).resolve()),input_sha256=sha(input_path),input_rows=len(observed),output_rows=len(fixed),
                input_predictor_fields=14,label_policy='income excluded from repair and output',before=before,after=after,automatic_modified_cells=len(automatic),
                manual_modified_cells=human_count,manual_review_cells=len(review),semantic_review_cases=len(result['semantic_cases']),deleted_rows=len(ids)-len(kept_ids),
                elapsed_seconds=elapsed,start_utc=json.loads(marker.read_text())['start_utc'],end_utc=now(),
                rollback=dict(original_sha256=signature(observed),restored_sha256=signature(restored),identical=True,metadata_and_row_order_restored=True),
                outputs={name:str((output/name).resolve()) for name in ['cleaned.csv','review.csv','detected_cells.csv','audit.jsonl','rolled_back.csv','repair_report.json','repair_report.md']})
    save(output/'repair_report.json',report)
    text=['# 数据清洗运行报告','',f'运行：{run_id}；冻结V3.3-J；输入{len(observed)}行、14预测字段，输出{len(fixed)}行。income不进入清洗输出。',
          f'自动净修改{len(automatic)}个单元；人工决定修改{human_count}个；待人工复核{len(review)}个；删除{len(ids)-len(kept_ids)}行。耗时{elapsed:.3f}秒。',
          '', '|指标|处理前|处理后再次检测|','|---|---|---|']
    for key in ['missing_cells','detected_cells','numeric_type_or_range_alerts','format_alerts','spelling_alerts','unknown_category_alerts','unit_conversion_proposals','cross_field_alert_cells']:
        text.append(f'|{key}|{before[key]}|{after[key]}|')
    text+=['','以上是训练参考/规则告警，不是人工注入真值；合法长尾及语义例外可能保留。处理后扫描仅量化剩余问题，不执行第二轮自动修复。',
           '原始缺失按字段统计：'+json.dumps(before['missing_by_field'],ensure_ascii=False),'',
           '审计正向重放及完整字段/元数据/行序回滚通过，SHA256：'+signature(restored),'', '## 输出文件']
    text.extend('- '+k+'：'+v for k,v in report['outputs'].items())
    (output/'repair_report.md').write_text('\n'.join(text),encoding='utf-8');save(output/'run_completed.json',dict(run_id=run_id,elapsed_seconds=elapsed,rollback_pass=True))
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,default=FINAL/'examples/independent_dirty.csv');p.add_argument('--output',type=Path,default=FINAL/'outputs/demo')
    p.add_argument('--seed',type=int,choices=CONFIG['seeds'],default=20260601);p.add_argument('--rate',type=float,choices=CONFIG['rates'],default=.1)
    p.add_argument('--deduplicate',action='store_true',help='Explicit optional end-stage deletion; OFF in every F1 experiment')
    p.add_argument('--review-decisions',type=Path,help='Explicit human decisions only; never used in independent F1 scoring')
    args=p.parse_args();r=run(args.input,args.output,args.seed,args.rate,args.deduplicate,args.review_decisions)
    print(json.dumps(dict(rows=r['input_rows'],automatic=r['automatic_modified_cells'],review=r['manual_review_cells'],report=r['outputs']['repair_report.md'],rollback=r['rollback']['identical']),ensure_ascii=True))


if __name__=='__main__':main()

"""Feature-only eligibility audit; does not open any sealed label CSV."""
import sys,json,random,itertools
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.paths import *


def main():
    freeze=json.loads((FINAL/'config/candidate_freeze.json').read_text(encoding='utf-8'))
    assert all(sha(FINAL/name)==expected for name,expected in freeze['files'].items())
    old=WORK/'V3.2';new=WORK/'V3.3';manifest=json.loads((new/'data/data_manifest.json').read_text(encoding='utf-8'))
    train_ids,train=feature_rows(FINAL/'test_fixtures/adult_features.csv');train_keys={feature_hash(r) for r in train}
    assert len(train)==32561
    used_test_ids=set();used_test_keys=set();old_manifest=json.loads((old/'data/data_manifest.json').read_text(encoding='utf-8'))
    for seed in CONFIG['seeds']:
        path=old/f'sealed/features_{seed}.csv';relative='sealed\\features_'+str(seed)+'.csv'
        assert sha(path)==old_manifest['files'][relative]
        ids,rows=feature_rows(path);used_test_ids.update(ids);used_test_keys.update(feature_hash(r) for r in rows)
    source=new/'data/adult.test';assert sha(source)==manifest['source_sha256']
    ids,external=feature_rows(source,uci=True);assert len(external)==16281
    seen=set();eligible=[];eligibility_counts=dict(train_identity_excluded=0,old_test_excluded=0,duplicate_excluded=0)
    for i,r in zip(ids,external):
        key=feature_hash(r)
        if key in train_keys:eligibility_counts['train_identity_excluded']+=1;continue
        if i in used_test_ids or key in used_test_keys:eligibility_counts['old_test_excluded']+=1;continue
        if key in seen:eligibility_counts['duplicate_excluded']+=1;continue
        seen.add(key);eligible.append(i)
    assert len(eligible)==manifest['external_eligible']
    if len(eligible)<8000:
        save(FINAL/'reports/independence_audit.json',dict(passed=False,available=len(eligible),required=8000,external_labels_opened=False))
        raise SystemExit('STOP: not enough genuinely unused feature identities; independent F1 acceptance not performed')
    shuffled=list(eligible);random.Random(20260601).shuffle(shuffled)
    assigned_keys=set();assigned_ids=set();selection=[];group_stats=[]
    for j,seed in enumerate(CONFIG['seeds']):
        expected=shuffled[j*1600:(j+1)*1600]
        assert expected==manifest['groups'][str(seed)],'Historical label-blind group assignment changed'
        path=new/f'sealed/features_{seed}.csv';assert sha(path)==manifest['files']['sealed\\features_'+str(seed)+'.csv']
        actual,rows=feature_rows(path);assert actual==expected and len(rows)==1600
        for position,(i,r) in enumerate(zip(actual,rows)):
            assert r==external[i]
            key=feature_hash(r);assert key not in train_keys|used_test_keys|assigned_keys and i not in used_test_ids|assigned_ids
            assigned_keys.add(key);assigned_ids.add(i)
            selection.append(dict(seed=seed,position=position,source='UCI Adult official adult.test',source_row_id=i,feature_sha256=key,native_missing_cells=sum(v is None for v in r.values())))
        group_stats.append(dict(seed=seed,n=1600,with_native_missing=sum(any(v is None for v in r.values()) for r in rows),features_sha256=sha(path)))
    # All recorded split sources are included conservatively in the train identity exclusion.
    usage=[];split_audit=[]
    scopes=[('V2',WORK/'最终提交V2'),('V3',WORK/'V3'),('V3.1',WORK/'V3.1'),('V3.2',old),('V3.3',new)]
    for stage,root in scopes:
        paths=list(root.glob('results/split_*.json'))+list(root.glob('data/development_split_*.json'))
        if stage=='V3.3':paths+=list((root/'stage3/inputs').glob('development_split_*.json'))
        for path in paths:
            obj=json.loads(path.read_text(encoding='utf-8'));mapping=obj.get('raw_ids',{})
            values={i for v in mapping.values() for i in v}
            if values:assert all(0<=i<32561 for i in values)
            split_audit.append(dict(stage=stage,file=str(path.relative_to(WORK)),sha256=sha(path),recorded_ids=len(values),all_excluded_by_original_train_universe=True))
        usage.append(dict(stage=stage,source='adult.data original training corpus',feature_universe_excluded=32561,split_metadata_files=len(paths),fresh_test_overlap=0,
                          note='All original training identities excluded, including profiles, historical tests, unit fixtures, tuning and later repeated development'))
    usage.append(dict(stage='V3.2 external',source='previously scored sealed feature groups',feature_universe_excluded=len(used_test_ids),split_metadata_files=5,fresh_test_overlap=0,note='Old external rows excluded by source ID and all 14 feature identity'))
    # Inspect source definitions and completion-marker inventory, never old score/probability tables.
    code_paths=[new/'prepare_fresh_test.py',new/'develop_v33.py',new/'stage2/run_experiments.py',new/'stage3/prepare.py',new/'stage3/run_cv.py',new/'stage3/compat_tests.py',old/'train_frozen.py',old/'predict_frozen.py']
    source_evidence=[dict(file=str(p.relative_to(WORK)),sha256=sha(p)) for p in code_paths]
    fresh_score_markers=list(new.glob('evaluation_*.json'))+list(new.glob('results/final_runs.csv'))+list(new.glob('results/frozen_test_predictions.csv'))
    assert not fresh_score_markers,'Fresh candidate pool has an existing scoring marker; stop and audit manually'
    audit=dict(passed=True,time_utc=now(),train_feature_universe=32561,prior_external_rows=len(used_test_ids),official_external_rows=16281,
               unused_unique_rows=len(eligible),selected_rows=8000,reserve_rows=len(eligible)-8000,groups=group_stats,
               selected_native_missing_rows=sum(g['with_native_missing'] for g in group_stats),historical_feature_overlap=0,prior_test_id_overlap=0,cross_group_overlap=0,
               eligibility_counts=eligibility_counts,external_labels_opened=False,label_based_sampling=False,
               source_evidence=source_evidence,prior_sealed_preparation_manifest_sha256=sha(new/'data/data_manifest.json'),
               qualification='Features previously used only for duplicate/eligibility and missingness coverage scans; labels were opaquely sealed, never fitted, selected, tuned or scored in recorded V3.3 runs',
               acceptance_population='user-approved complete and naturally incomplete fresh official test rows; not the old complete-case test population')
    csvsave(FINAL/'reports/independent_test_assignment.csv',selection);csvsave(FINAL/'reports/history_usage_ledger.csv',usage);csvsave(FINAL/'reports/history_split_checks.csv',split_audit)
    save(FINAL/'reports/independence_audit.json',audit)
    save(PRIVATE/'data/fresh_group_locations.json',{str(seed):dict(features=str(new/f'sealed/features_{seed}.csv'),labels=str(new/f'sealed/labels_{seed}.csv'),expected_labels_sha256=manifest['files']['sealed\\labels_'+str(seed)+'.csv']) for seed in CONFIG['seeds']})
    lines=['# 独立数据来源与历史使用审计','',f'核验通过：剩余{len(eligible)}条唯一未用于拟合/验证/选模/评分的官方adult.test记录，保持原标签盲选五组×1600，实际选用8000，余留{len(eligible)-8000}。',
           f'选用记录中{audit["selected_native_missing_rows"]}条含原生缺失。五组互不重叠；与全部32561条adult.data特征身份及V3.2旧8000测试记录的ID/14字段特征交集均为0。',
           '', '历史V2、V3、V3.1、V3.2及V3.3全部开发、画像、参考、交叉验证和单元夹具记录均保守纳入adult.data全集排除，不使用仅剩的18条历史候选。旧外部测试记录不重新命名。',
           '', '新总体特征曾用于资格排重和原生缺失覆盖统计，标签曾仅作封装和哈希；不能声称“从未读取过”。审计口径为未用于训练、验证、调参、模型选择或评分。源码及已完成运行的记录支持此边界。',
           '', '分组是此前固定20260601一次洗牌后的连续五段，已重新计算并与旧盲选清单及特征SHA完全匹配。未查看income分布、未改变类别比例、未删除不利记录。原生缺失总体已经用户批准，与旧完整病例成绩不可作直接因果差分。',
           '', '本次审计不打开任何sealed/labels CSV，不读取旧外部评分表。原始文件SHA只作不解析标签的完整性校验。源码证据、历史分区摘要、源行索引和特征哈希随报告保存。最终评分将在全部模型和预测冻结后单独开始。']
    (FINAL/'reports/独立数据审计报告.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(passed=True,unused=len(eligible),selected=8000,native_missing=audit['selected_native_missing_rows']),ensure_ascii=True))


if __name__=='__main__':main()

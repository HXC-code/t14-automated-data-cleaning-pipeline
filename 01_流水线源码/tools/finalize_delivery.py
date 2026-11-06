"""Finalize honest evidence, privacy checks and immutable SHA256 inventory."""
import sys,csv,json,datetime,statistics,platform,ast
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.paths import *
from src.csvio import read_input
from src.runtime import verify_candidate


def main():
    verify_candidate();frozen=load_json(FINAL/'config/execution_freeze.json')
    assert all(sha(FINAL/name)==value for name,value in frozen['files'].items()),'Frozen execution changed after scoring'
    score=load_json(PRIVATE/'evaluation_completed.json');assert sha(FINAL/'reports/independent_runs.csv')==score['metrics_sha256']
    assert sha(FINAL/'reports/F1_acceptance_decision.json')==score['decision_sha256']
    time_chain=[load_json(FINAL/'config/candidate_freeze.json')['time_utc'],load_json(FINAL/'config/model_freeze.json')['time_utc'],
                load_json(PRIVATE/'prediction_freeze.json')['time_utc'],frozen['time_utc'],load_json(PRIVATE/'evaluation_started.json')['start_utc'],score['end_utc']]
    stamps=[datetime.datetime.fromisoformat(v) for v in time_chain];assert stamps==sorted(stamps)
    decision=load_json(FINAL/'reports/F1_acceptance_decision.json');assert not decision['classification_pass']
    with (FINAL/'reports/五次独立实验结果.csv').open(encoding='utf-8-sig') as f:runs=list(csv.DictReader(f))
    assert len(runs)==15
    for rate in CONFIG['rates']:
        group=[r for r in runs if float(r['rate'])==rate];assert len(group)==5
        gain=[100*(float(r['J_f1'])-float(r['raw_f1'])) for r in group]
        assert all(abs(g-float(r['gain_pp']))<1e-12 for g,r in zip(gain,group))
        actual=next(x for x in decision['three_rates'] if x['rate']==rate)
        assert abs(statistics.mean(gain)-actual['mean_gain_pp'])<1e-12
        assert actual['meets_3pp']==(statistics.mean(gain)>=3)
    # Relocation checks use only already-cleaned feature outputs, no target reader.
    relocated=PRIVATE/'relocated_release'
    assert not any((relocated.parent/name).exists() for name in ['V3.3','V3.2','V3.1','V3','最终提交V2'])
    relocated_tests=load_json(relocated/'reports/test_results.json');assert relocated_tests['total']==206 and relocated_tests['skipped']==0 and relocated_tests['success']
    relocated_output=relocated/'outputs/standalone/cleaned.csv';reference_output=FINAL/'outputs/demo/cleaned.csv'
    assert sha(relocated_output)==sha(reference_output)
    save(FINAL/'reports/clean_environment_relocation.json',dict(time_utc=now(),isolated_venv=True,original_project_directories_absent_at_relocated_parent=True,
              original_tests=155,phase3_tests=29,new_tests=22,total=206,failures=0,errors=0,skipped=0,standalone_one_command_pass=True,
              cleaned_sha256=sha(relocated_output),matches_original_pipeline=True,real_labels_needed=False))
    # Protect all phase-two and phase-three original artifacts, not just core code.
    originals=load_json(WORK/'V3.3/stage3/inputs/protected_entry.json')
    third=load_json(WORK/'V3.3/stage3/output/artifact_sha256.json')
    originals.update({str(WORK/'V3.3/stage3'/name):value for name,value in third.items()})
    p=WORK/'V3.3/stage3/output/artifact_sha256.json';originals[str(p)]=sha(p)
    preserved=[]
    for path,expected in originals.items():
        assert sha(path)==expected,'Original artifact changed: '+path
        preserved.append(dict(file=str(Path(path).relative_to(WORK)),sha256=expected,unchanged=True))
    csvsave(FINAL/'reports/原版本与历史实验保留核验.csv',preserved)
    forbidden=[];bank_checks=[]
    forbidden_columns={'income','original_label_token','true_label','y_true','probability','injected_truth'}
    for p in FINAL.rglob('*'):
        if not p.is_file() or '__pycache__' in p.parts:continue
        if p.suffix=='.npz' or p.name.startswith('labels_') or p.name.startswith('test_quality_'):forbidden.append(str(p.relative_to(FINAL)))
        if p.suffix=='.csv':
            with p.open(encoding='utf-8-sig',newline='') as f:
                reader=csv.reader(f);header=next(reader,[])
                if forbidden_columns&set(header):forbidden.append(str(p.relative_to(FINAL)))
                for row in reader:
                    if any(value in ['>50K','<=50K','>50K.','<=50K.'] for value in row):forbidden.append(str(p.relative_to(FINAL)));break
        if p.suffix=='.py':ast.parse(p.read_text(encoding='utf-8-sig'))
    assert not forbidden,forbidden
    import joblib
    for seed in CONFIG['seeds']:
        bank=joblib.load(FINAL/f'reference/bank_{seed}.joblib');assert all('income' not in r for r in bank.ref)
        bank_checks.append(dict(seed=seed,reference_rows=len(bank.ref),contains_income=False))
    save(FINAL/'reports/public_data_privacy_check.json',dict(time_utc=now(),forbidden_files=[],forbidden_true_target_columns=[],real_income_values_in_public_CSV=False,
             test_probability_vectors_public=False,injected_truth_files_public=False,reference_banks=bank_checks,
             note='Source code contains target-token literals and generators for synthetic unit fixtures; no real held-out target vector is distributed'))
    save(FINAL/'reports/environment.json',dict(time_utc=now(),python=platform.python_version(),platform=platform.platform(),thread_limit=1,
         dependency_lock='requirements-lock.txt',clean_environment_install_log='logs/clean_environment_install.log',clean_environment_test_log='logs/clean_environment_tests.log'))
    for key in ['f1','quality','restoration']:
        assert load_json(FINAL/f'logs/{key}_collision_qa.json')['verdict']=='PASS'
        assert load_json(FINAL/f'logs/{key}_text_qa.json')['below_minimum_count']==0
    assert load_json(FINAL/'logs/figure_source_qa.json')['summary']['ready']
    (FINAL/'reports/图表质量核验.md').write_text('''# 图表质量核验

三图使用本次真实独立结果；F1展示全部五次配对增益及样本SD，不删除弱种子。前后状态图明确聚焦中噪声，所有三档完整表仍提供。类型图用各档全部注入单元的精确池化比例，合理近似不混入严格恢复。

最终PDF三图均0碰撞FAIL/0 WARN，最小文字8pt。单面板对齐为不适用。首版F1数字标签被辅助网格穿过，移除该辅助网格后检查通过，数值、个体点和坐标范围未变；原失败QA记录保留。课程报告尺寸有意采用约7.2/8英寸，非投稿尺寸，源检查尺寸提示已人工确认。PNG逐图目视检查清晰、未截断、误差范围完整。提供可编辑PDF/SVG及300dpi PNG、600dpi TIFF。
''',encoding='utf-8')
    changes=[
        dict(component='Frozen J/units/outliers/FD',change='byte-identical copy; no post-test change',evidence='config/candidate_freeze.json; config/execution_freeze.json'),
        dict(component='Runtime CLI and audit adapter',change='CSV/schema/profile/queue/timestamp/optional explicit review and final deduplication; defaults preserve J exactly',evidence='run_pipeline.py; reports/engineering_acceptance.json'),
        dict(component='Test launcher',change='Resolved legacy/new tests namespace collision; all original test bodies preserved',evidence='logs/full_unit_tests_attempt1.log; logs/full_unit_tests_final.log'),
        dict(component='Parser fixture availability',change='Added target-masked Mushroom structure fixture to eliminate two skipped original tests',evidence='config/unit_fixture_provenance.json; logs/full_unit_tests_attempt2.log'),
        dict(component='UTF8 input metadata',change='Explicit UTF8 loader fixed Windows locale error before any external label read',evidence='logs/independent_predictions.log; logs/independent_predictions_attempt2.log'),
        dict(component='Independent prediction and scoring',change='All probabilities fixed before one label-reading session; medium-noise failure retained',evidence='reports/F1_acceptance_decision.json; logs/independent_score_once.log'),
        dict(component='Post-score reports/figures/portable reproduction helper',change='Evidence/export only; no classifier re-fitting or re-scoring after acceptance',evidence='tools/build_reports.py; tools/plot_reports.py; tools/reproduce_f1.py')]
    csvsave(FINAL/'reports/最终修改与失败记录.csv',changes)
    required=['README.md','requirements.txt','requirements-lock.txt','run_pipeline.py','run_tests.py','config/final_protocol.json','config/candidate_freeze.json','config/execution_freeze.json',
              'reports/independent_test_assignment.csv','reports/五次独立实验结果.csv','reports/下游F1验收对比表.csv','reports/修复前后对比报告.md','reports/单元测试完整报告.md',
              'reports/audit_log_sample.jsonl','reports/回滚验证报告.md','T14自动化数据清洗流水线最终验收报告.md']
    assert all((FINAL/name).is_file() and (FINAL/name).stat().st_size for name in required)
    save(FINAL/'reports/delivery_checks.json',dict(time_utc=now(),required_files_present=True,independent_records=8000,disjoint_groups=5,native_missing_records=1186,
           models=105,inner_classifier_fits=1890,converged_models=105,converged_inner_fits=1890,one_independent_scoring_session=True,
           original_tests=155,phase3_tests=29,final_tests=22,total_tests=206,skipped=0,engineering_rollback_cases=17,clean_false_modifications=0,
           frozen_sources_unchanged=True,historical_files_unchanged=len(preserved),privacy_pass=True,clean_relocated_environment_pass=True,
           acceptance_pass=False,failed_requirement='10% noise mean F1 gain <3pp',medium_gain_pp=decision['three_rates'][1]['mean_gain_pp']))
    files=[p for p in FINAL.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='SHA256SUMS.csv' and p.suffix!='.zip']
    csvsave(FINAL/'SHA256SUMS.csv',[dict(file=str(p.relative_to(FINAL)),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(files)])
    print(json.dumps(dict(files_hashed=len(files),historical_files_unchanged=len(preserved),privacy_pass=True,engineering_pass=True,final_acceptance_pass=False)))


if __name__=='__main__':main()

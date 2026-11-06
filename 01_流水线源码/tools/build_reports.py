"""Task-book verdict from the one completed independent evaluation."""
import sys,platform,statistics,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from src.paths import *
from src.csvio import read_input


def md(frame,digits=4):
    def f(c,x):
        if isinstance(x,(float,)):
            if c in ['rate','噪声等级']:return f'{x:.0%}'
            return f'{x:.{digits}f}'
        return str(x)
    return '|'+ '|'.join(map(str,frame.columns))+'|\n|'+'|'.join(['---']*len(frame.columns))+'|\n'+'\n'.join('|'+ '|'.join(f(c,x) for c,x in zip(frame.columns,row))+'|' for row in frame.itertuples(index=False,name=None))+'\n'


def write(name,text):
    (FINAL/'reports'/name).write_text(text,encoding='utf-8')


def main():
    decision=load_json(FINAL/'reports/F1_acceptance_decision.json');engineering=load_json(FINAL/'reports/engineering_acceptance.json');tests=load_json(FINAL/'reports/test_results.json')
    assert (PRIVATE/'evaluation_completed.json').exists()
    assert tests['success'] and tests['skipped']==0
    f1=pd.read_csv(FINAL/'reports/下游F1验收对比表.csv');runs=pd.read_csv(FINAL/'reports/五次独立实验结果.csv');q=pd.read_csv(FINAL/'reports/independent_repair_quality.csv')
    totals=q.groupby('rate')[['n','injected','detected','automatic_modified','strict_modified','strict_restored','reasonable_only','wrong_modified','clean_misrepair','clean_cells','manual_review','semantic_cases']].sum().reset_index()
    totals['automatic_precision']=totals.strict_modified/totals.automatic_modified;totals['strict_restoration_rate']=totals.strict_restored/totals.injected;totals['clean_misrepair_rate']=totals.clean_misrepair/totals.clean_cells
    totals.to_csv(FINAL/'reports/独立修复质量汇总.csv',index=False,encoding='utf-8-sig')
    profiles=pd.read_csv(FINAL/'reports/修复前后质量统计.csv');profile_sum=profiles.groupby(['rate','state']).sum(numeric_only=True).drop(columns=['seed']).reset_index()
    profile_sum.to_csv(FINAL/'reports/修复前后质量汇总.csv',index=False,encoding='utf-8-sig')
    types=pd.read_csv(FINAL/'reports/各错误类型修复统计.csv').groupby(['rate','type']).sum(numeric_only=True).drop(columns=['seed']).reset_index()
    types.to_csv(FINAL/'reports/各错误类型修复汇总.csv',index=False,encoding='utf-8-sig')
    precision=totals[['rate','automatic_modified','strict_restored','reasonable_only','automatic_precision','strict_restoration_rate','clean_misrepair','manual_review']].copy()
    precision.automatic_precision*=100;precision.strict_restoration_rate*=100
    precision_human=precision.rename(columns={'rate':'噪声等级','automatic_modified':'自动修改数','strict_restored':'严格原值还原数','reasonable_only':'合理近似数','automatic_precision':'自动精确率/%','strict_restoration_rate':'严格还原率/%','clean_misrepair':'清洁误修数','manual_review':'待复核数'})
    profile_human=profile_sum[['rate','state','missing_cells','detected_alert_cells','spelling_alerts','format_alerts','unit_conversion_proposals','cross_field_alert_cells','auto_modified','manual_review']].rename(columns={'rate':'噪声等级','state':'数据状态','missing_cells':'缺失单元','detected_alert_cells':'检测告警单元','spelling_alerts':'拼写告警','format_alerts':'格式告警','unit_conversion_proposals':'量纲候选','cross_field_alert_cells':'跨字段告警','auto_modified':'自动修改','manual_review':'待复核'})
    write('修复前后对比报告.md',f'''# 本次独立验收修复前后对比

数据是本次真正独立的五组×1600官方Adult测试记录，含1186条原生缺失记录。每档使用同一8000条身份，跨噪声档并非24000条全新样本。表中各档为五组累计，清洗处理14预测字段；income独立保留，不进入任何修复输入。

## 原始、注入、修复状态

original指未做本次人工注入的原始基准，仍含原生缺失，并非所有字段都已知完整正确。dirty由原生成器注入；J为冻结单次自动修复。检测指标是训练参考/规则告警，可能含合法长尾和语义例外，不当作真实错误标签。各告警类别可重叠，不能相加当总异常数。

{md(profile_human)}

前两状态没有提交修复/人工决定，动作数为0不表示没有问题；J的manual_review是待人工清单，未冒充已经人工完成。处理后再次扫描仅做量化，不执行第二轮修复。源标称3%/10%/20%沿用旧注入配额；因跳过零值×1000、已占用字段等，实际注入量以CSV为准，未为达标改配额或删样本。

## 严格恢复与合理近似

下表precision、restoration为百分比，数量按净变化单元计数。自动精确率=修改后严格等于原值/全部净修改；严格还原率=严格恢复注入单元/全部注入单元。reasonable_only只表示非原值但符合训练字段类型/范围的近似，仍计入wrong_modified，不计严格成功。不能把分类器内SimpleImputer结果计作流水线恢复。

{md(precision_human)}

J保留缺失及其原始标记，因此缺失数量不会像填补策略那样减少；fnlwgt低支持覆盖值可能继续越界并进入复核。逻辑/合法教育数字冲突无法判断哪一侧污染时保留。约95%修改精确率和零清洁单元误修不意味着全面恢复原始数据，复核量及剩余错误不能省略。

## 注入错误的离线残余

真值仅由独立离线量化程序使用；未进入实际修复。类型range为原覆盖注入，unit为原量纲注入。完整分组明细在各错误类型修复统计.csv。

{md(types)}

![中噪声质量对比](../figures/中噪声修复前后质量对比图.png)

![严格恢复率](../figures/各错误类型严格原值还原图.png)

本次中噪声F1增益仍仅2.8820421159908305pp，低于3。数据质量诊断没有被用来在测试后修改J或再次评分。
''')
    rollback=pd.read_csv(FINAL/'reports/rollback_cases.csv')
    write('回滚验证报告.md',f'''# 实际回滚验证报告

本次17个持久化运行全部通过正向重放及逆序回滚：15个独立数据视图，每个1600行；另有实际删除能力与显式复核能力合成夹具各1个。后两项不进入任何F1或独立质量汇总。

删除夹具4行在修复后明确删除2个重复行，日志保留原位置与删除前快照；回滚先恢复行位，再逆序撤销同单元事件，最后还原新增缺失标记。多个修复事件同字段、连续删除、元数据存在性和原行序均有专项测试。独立测试数据没有启用删除。

{md(rollback[['scope','seed','rate','input_rows','output_rows','deleted','identical','duplicate_source_events']])}

SHA256针对规范化完整预测字段字典及原有元数据，逐字段内容和行序相同；不是宣称CSV换行/数字排版字节一致。原始输入文件未改，另有输入文件与审计文件字节SHA。income从未进入工作表，私有标签文件保持预封存SHA不变。

全部原始/回滚哈希和审计文件哈希见rollback_cases.csv。完整audit.jsonl及rolled_back.csv位于各outputs子目录。audit_log_sample.jsonl摘自本次真实1600行运行，不是手写示例。事件包含标识、字段、before/after、原因/规则、UTC时间及实际结果；review的before==after明确表示未修改。

另以tools/rollback_data.py仅输入cleaned.csv与audit.jsonl，不读取原始输入文件，分别恢复了1600行独立脏特征和含删除的4行夹具，标识从审计record_order恢复，SHA匹配原运行报告。日志为audit_only_independent_restore.log和audit_only_deletion_restore.log。
''')
    write('单元测试完整报告.md',f'''# 本次单元测试与干净环境报告

原155项、第三阶段29项、本次新增22项，共206项，失败0、错误0、跳过0。原有测试体逐字冻结，源码未改。

公开夹具只保存历史训练的14字段特征，income在单元夹具中按固定规则合成，不是真实测试标签。原Mushroom解析器的两项结构测试使用其22字段及统一的无真实类别标记。它们只验证读取结构，不用于Adult任何分类实验。F1验收始终用隔离的私有真实标签，未用合成目标替代。

完整日志：logs/full_unit_tests_final.log、logs/clean_environment_tests.log、logs/relocated_environment_tests.log。原有155项和29项的逐项名称、20余项工程路径及结果均在日志，不只提供汇总。

初次工程入口发生tests包重名导入错误；随后因原结构数据夹具缺失出现2项跳过；补齐不带真实目标的结构夹具后无跳过。预测准备曾因Windows默认文本编码读取含中文路径的UTF8元数据失败，已在打开任何测试标签前修正为显式UTF8。对应attempt日志均保留，没有删除失败记录，也没有改动J规则或重新选模。

使用全新、无system-site-packages的Python虚拟环境，按requirements.txt安装，requirements-lock.txt记录完整依赖。又将公开交付内容复制到不含原工程的另一位置，在该环境重跑206项测试及一键入口。输出与本次冻结J视图逐单元一致，cleaned.csv SHA一致。部署不依赖Codex手动改数据或工作区中的历史模型路径。

本次22项覆盖冻结一致性、唯一正式验收规则、同预算/阈值、目标泄漏隔离、UTF8元数据、一次性评分保护、缺失/fnlwgt/语义/FD/单位/长尾、完整字段审计、连续删除恢复、同字段多事件、显式复核、输入校验、实际一键输出和防覆盖。
''')
    f1view=f1.copy();f1view['meets_3pp']=f1view.meets_3pp.map({True:'是',False:'否'})
    f1view=f1view.rename(columns={'rate':'噪声等级','mean_gain_pp':'平均增益/pp','sample_sd_pp':'样本标准差/pp','meets_3pp':'达到3pp'})
    write('独立F1验收报告.md',f'''# 冻结后的独立F1验收

唯一正式标准：每档五次配对增益均值≥3个百分点，三档分别满足；不用CI下限、修复精确率90%、总体均值或挑选单次结果替代。第三阶段额外稳定性门槛不参与本次验收。

{md(f1view,6)}

中噪声未达标，差值为3−2.8820421159908305=0.1179578840091695个百分点。不能通过四舍五入变为达标，最终F1验收不通过。

每组1600行，5组互不重叠，合计8000唯一记录；相同五组复用于3档，训练样本跨种子也可能重叠，不能称为15份互斥独立样本。分组早于J开发固定，未看income重采样。1186条含原生缺失；特征仅曾做资格排重/覆盖扫描，历史训练、选模、调参、旧测试身份交集为0，详见独立数据审计报告。

训练采用原3520/880各自固定注入再拼为4400，参考3400独立。每版本同3折内层、C={{0.1,1,10}}×权重={{None,balanced}}的18次预算，选训练内平均F1，精确平局取首个，选定后拟合全部4400。保持StandardScaler、原缺失标记流程、LBFGS1000轮及0.5阈值。训练/验证拟合填补、编码、标准化，不使用任何测试标签。所有1890内层及105最终拟合收敛。全部105套预测先冻结，之后一次读取5个封存标签文件评分；评价完成标记禁止再次独立评分。

每次ΔF1=(F1_J−F1_raw)×100，先算全精度配对差，再求均值和ddof=1样本SD。Accuracy、Precision、Recall、F1、AUC及全部基准在independent_runs.csv和全部基准同步重测.csv；五次细节如下。

{md(runs,6)}

新总体包含自然缺失，不能将旧外部2.943或第三阶段开发CV与此直接作算法因果差分。同步基准只用于描述，不允许测试后改选另一版本宣布J通过。

![独立F1增益](../figures/下游F1独立验收图.png)
''')
    demo=load_json(FINAL/'outputs/demo/repair_report.json')
    rows=[
        dict(requirement='一键运行',actual=f"1600行接入→画像/检测/定位→J修复→复核清单→输出；自动{demo['automatic_modified_cells']}、待复核{demo['manual_review_cells']}",passed=True,evidence='run_pipeline.py; logs/one_click.log; outputs/demo/repair_report.json'),
        dict(requirement='修复报告',actual='本次实际规模、缺失、告警、修改、复核、前后对比、耗时及输出路径均自动生成',passed=True,evidence='outputs/demo/repair_report.md; outputs/clean_environment_run/repair_report.json'),
    ]
    for rate,name in [(.03,'低噪声'),(.1,'中噪声'),(.2,'高噪声')]:
        r=next(x for x in decision['three_rates'] if x['rate']==rate)
        rows.append(dict(requirement='下游F1'+name,actual=f"{r['mean_gain_pp']:.10f} pp；样本SD {r['sample_sd_pp']:.10f}",passed=r['meets_3pp'],evidence='reports/下游F1验收对比表.csv; reports/五次独立实验结果.csv'))
    rows.extend([
        dict(requirement='流水线源码',actual='冻结J及完整依赖、入口、训练/一次评分/复现脚本、requirements和SHA清单',passed=True,evidence='src/; frozen/; tools/; config/; README.md; SHA256SUMS.csv'),
        dict(requirement='单元测试',actual='155+29+22=206；0失败、0错误、0跳过；独立环境及迁移目录重跑',passed=True,evidence='reports/test_results.json; logs/clean_environment_tests.log; logs/relocated_environment_tests.log'),
        dict(requirement='修复前后对比',actual='本次独立数据三状态、三档及八种注入类型；原值恢复与合理近似分列',passed=True,evidence='reports/修复前后对比报告.md; reports/修复前后质量统计.csv; figures/'),
        dict(requirement='audit log样例',actual='真实运行的时间戳、记录/字段、前后值、原因、规则、结果；17条持久化链回滚通过',passed=True,evidence='reports/audit_log_sample.jsonl; reports/回滚验证报告.md; outputs/*/audit.jsonl')
    ])
    csvsave(FINAL/'reports/任务书逐项验收.csv',rows)
    table=pd.DataFrame(rows);table['passed']=table.passed.map({True:'是',False:'否'});overall=all(r['passed'] for r in rows)
    table=table.rename(columns={'requirement':'验收要求','actual':'实际结果','passed':'是否达标','evidence':'证据文件'})
    assert not overall and not decision['classification_pass']
    baseline=pd.read_csv(FINAL/'reports/全部基准同步重测.csv').pivot(index='version',columns='rate',values='mean_gain_pp').reset_index().rename(columns={.03:'3%',.1:'10%',.2:'20%'})
    final=f'''# T14自动化数据清洗流水线最终验收报告

## 正式结论：未通过最终验收

冻结V3.3-J在真正独立数据上，低/中/高噪声平均F1增益分别为+4.0247608613、+2.8820421160、+3.3446632655个百分点。中噪声低于任务书3个百分点要求，因此不得宣布最终通过。工程完整性、数据质量精确率及第三阶段开发成绩均不能替代这一条件。

本次按任务书原有条件判断，没有追加旧开发阶段的CI门槛，也没有删去任何正式验收项。测试后未改规则、参数、阈值、种子、行数、类别分布或评价公式，未重跑评分追分。

## 任务书逐项验收

{md(table)}

端到端复用和检测→定位→修复→复核闭环由统一入口、detected_cells.csv、cleaned.csv、review.csv及显式复核输入接口实现；真实量化由本次独立F1、修复质量、前后状态和审计回滚提供。真实待复核清单不冒充已经人工核准。删除只在独立的合成能力夹具启用，全部F1测试保留1600行。

## 五次独立结果

{md(f1view,6)}

每档均完整保留五个预定种子。8000条身份为五个互斥分组，包含1186条原生缺失，未按标签重采样；同一记录可在三个噪声档重复，不冒称24000条不同测试数据。

## 同步重测全部基准

以下是相同新总体和统一分类器预算下的F1增益pp，仅作诊断，不能在看过测试后挑其中一项替换J。V2采用保留旧修复器、独立参考域与训练脏数据统计的兼容重测；不是重新使用测试数据拟合V2。所有版本都不使用income修复特征。

{md(baseline)}

## 修复质量与局限

{md(precision_human)}

修改精确率约95%、非注入清洁单元误修0，但严格还原率约54%–56%，大量缺失、覆盖及语义不确定项保留复核。不能将合理插补或分类器内插补计为原值恢复。中噪声弱组20260601增益仅0.3827pp，未删除该组；其他四组也全部进入均值。有限分组波动和未恢复的信息都是限制，当前证据不足以给出单一操作的因果归因。

## 冻结、隔离及交付

candidate_freeze.json固定第三阶段实际J源码和参考模型；model_freeze.json固定训练内选出的105个模型；execution_freeze.json和私有预测清单早于标签读取。J在15组训练视图上与第三阶段完全一致，15组独立数据的工程入口输出也与评分J视图一致。完整源码及配置哈希、真实日志、数据索引和特征哈希均交付，原V2/V3/V3.1/V3.2及第三阶段结果不覆盖。

真实测试标签、人工注入真值、逐行测试概率和带真实目标的私有工作数据不进入公开交付目录。公开夹具只含特征及合成目标生成规则。独立安装环境和迁移目录中206项测试及实际一键入口均通过，CSV内容SHA一致。

正式测试已消费本次8000条，当前原审计池只余249条，不能按原五组×1600协议再建立同规模独立验收。若以后优化，必须在开发数据中进行并补充足够未用的同目标总体有标签记录；不能反复用本次结果选参数，也不能把机械复现称为新的独立测试。

本包是“工程交付完整、独立F1中噪声未达标”的真实归档，不是最终性能通过证书。
'''
    (FINAL/'T14自动化数据清洗流水线最终验收报告.md').write_text(final,encoding='utf-8')
    save(FINAL/'reports/final_verdict.json',dict(time_utc=now(),overall_pass=False,classification_pass=False,failed_requirements=['下游F1中噪声'],
             exact_medium_mean_pp=decision['three_rates'][1]['mean_gain_pp'],official_requirements_only=True,additional_CI_gate=False,engineering_pass=True,
             single_independent_scoring=True,external_test_records=8000,public_test_labels=False,truth_exported=False))
    (FINAL/'README.md').write_text('''# T14 自动化数据清洗流水线 V3.3-J 最终交付

**最终验收未通过：中噪声独立F1平均增益2.8820421159908305pp，低于3pp。** 低噪声4.0247608613019965pp，高噪声3.344663265463148pp。项目源码、工程能力和真实证据完整交付，不把开发结果当独立达标。

## 干净环境一键运行

在本目录打开PowerShell，使用Python 3.14（本次3.14.6）：

```powershell
python -m venv ../t14_clean_env
../t14_clean_env/Scripts/python.exe -m pip install -r requirements-lock.txt
../t14_clean_env/Scripts/python.exe -B run_pipeline.py --input examples/independent_dirty.csv --output outputs/my_run
```

这一个入口完成CSV接入、质量画像、训练参考规则/统计检测、单元定位、冻结J修复、人工复核清单、结果及报告输出。样例为本次独立验收固定第一组的10%脏特征，1600行，无income、无注入真值。无需Codex手工改数据或额外准备历史目录；reference内已含冻结、无income预测特征的参考模型。输出目录必须是新的运行名，已有run_started会拒绝覆盖。自有Adult格式数据可替换--input。

输出：cleaned.csv、detected_cells.csv、review.csv、repair_report.md/json、audit.jsonl、rolled_back.csv。报告数字、耗时、路径来自该次运行。可用--seed指定五个既有参考配置之一，--rate指定保留的实验视图配置；默认20260601/10%，不是根据输入真值估计噪声。J不填统计缺失，不猜fnlwgt原值，不把Husband/Wife当绝对性别；可靠教育映射、单位和V3.1显式孤立值动作保留。

CSV必须包含14个预测字段，可带record_id或source_row_id；income不作为清洗输入，也不写入输出。带表头CSV保留类别空格供真实规范化审计；?及空值识别为缺失。非法数值schema会定位报错并保留原文件，不静默丢行。原始15列无表头UCI格式也可读取，目标列忽略。

字段顺序/名称：age, workclass, fnlwgt, education, education_num, marital_status, occupation, relationship, race, sex, capital_gain, capital_loss, hours_per_week, native_country。

## 人工复核和删除能力

review.csv含decision/new_value/reason空列。只有明确填写approve或keep并提供文件后才应用：

```powershell
python -B run_pipeline.py --input examples/independent_dirty.csv --output outputs/reviewed_run --review-decisions my_decisions.csv
```

这些显式操作单独审计，不能伪装为自动恢复。独立F1验收没有输入人工决定。--deduplicate为显式可选末端去重，默认关闭；本次所有F1组未删除任何样本。实际删除与复核能力演示使用examples中的合成夹具，均可从日志完整回滚。

只需清洗输出和审计即可恢复，无需读取原始输入文件：

```powershell
python -B tools/rollback_data.py --cleaned outputs/my_run/cleaned.csv --audit outputs/my_run/audit.jsonl --output outputs/my_run/restored_from_log.csv --expected-report outputs/my_run/repair_report.json
```

## 测试和完整性

```powershell
../t14_clean_env/Scripts/python.exe -B tools/verify_delivery.py
../t14_clean_env/Scripts/python.exe -B run_tests.py
```

原155+第三阶段29+新增22共206项，无失败/错误/跳过。测试使用实际训练特征和确定性合成income，不分发真实测试标签。两项Mushroom读取结构夹具也不含其真实类别。完整逐项日志在logs；首次导入/缺夹具/文本编码问题的原日志均保留，未改J或原测试体。

先验包再执行新运行；重跑测试会刷新测试报告时间等派生证据，建议在交付副本中运行以保持原快照。冻结源码和正式实验CSV不要修改，流水线输出用新目录名。

## 独立评价和机械复现

正式数据来自原UCI Adult官方测试文件，按冻结清单排除全部历史训练/旧测试身份。五组各1600、共8000互斥记录，含1186条原生缺失；未按income分组。源索引/特征哈希见reports/independent_test_assignment.csv，审计见reports/独立数据审计报告.md。

全部模型与预测在一次评分前冻结。每版本用原4400训练行、同3折六候选预算、StandardScaler、0.5阈值。真值只用于离线质量量化。任务书只按三档五次F1配对增益均值≥3判断；此前开发CI门槛不参与本次结论。

真实income、注入真值与逐行概率保留在交付目录之外，不公开。若有获准的原始UCI文件，可将其置于本目录之外，再机械复现已经评分的固定测试：

```powershell
python -B tools/reproduce_f1.py --adult-train ../private_data/adult.data --adult-test ../private_data/adult.test --output ../t14_reproduction_private
```

脚本核验config/dataset_sources.json的原文件SHA，严格复用当前索引、噪声、参数预算和冻结J，所有预测完成后才解码测试目标。输入和输出必须在公开目录外，输出必须新建；不需要原始历史版本目录。**这是已知测试的机械复现，不是新的独立验收，更不能据此继续调参。** 原正式评分工具score_once有一次性标记保护，不能在当前实验重复运行。UCI来源地址与DOI保存在dataset_sources.json；数据不随公开包分发。

## 交付索引

- T14自动化数据清洗流水线最终验收报告.md：唯一正式结论和逐项证据。
- reports/下游F1验收对比表.csv、五次独立实验结果.csv：全精度五次结果及逐档判断。
- reports/independent_runs.csv、全部基准同步重测.csv：Accuracy/Precision/Recall/F1/AUC及历史基准同总体重测。
- reports/修复前后对比报告.md、回滚验证报告.md、单元测试完整报告.md、独立F1验收报告.md。
- reports/audit_log_sample.jsonl与outputs各实际运行：真实时间戳审计及回滚。
- src/、frozen/、tools/、config/、reference/：完整可运行源码、冻结依赖、参数和无目标参考模型。
- SHA256SUMS.csv：全部公开交付文件哈希；config内另有候选/模型/执行冻结清单。

三个噪声条件共用8000身份，不宣称24000独立样本；原始基准包含自然缺失。合理近似仍计非严格恢复，分类器内插补不写回流水线。中噪声未达标的事实不因工程成功或约95%修改精确率而改变。
''',encoding='utf-8')
    print(json.dumps(dict(overall_pass=False,failed='medium F1',source='single frozen independent evaluation'),ensure_ascii=True))


if __name__=='__main__':main()

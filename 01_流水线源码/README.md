# T14 自动化数据清洗流水线 V3.3-J 最终交付

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

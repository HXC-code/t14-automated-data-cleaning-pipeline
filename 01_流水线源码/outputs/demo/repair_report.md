# 数据清洗运行报告

运行：3b5d6adba1d749d79310330f196a7cac；冻结V3.3-J；输入1600行、14预测字段，输出1600行。income不进入清洗输出。
自动净修改1077个单元；人工决定修改0个；待人工复核1420个；删除0行。耗时1.074秒。

|指标|处理前|处理后再次检测|
|---|---|---|
|missing_cells|579|579|
|detected_cells|2497|1426|
|numeric_type_or_range_alerts|452|114|
|format_alerts|366|0|
|spelling_alerts|373|0|
|unknown_category_alerts|8|8|
|unit_conversion_proposals|238|0|
|cross_field_alert_cells|551|565|

以上是训练参考/规则告警，不是人工注入真值；合法长尾及语义例外可能保留。处理后扫描仅量化剩余问题，不执行第二轮自动修复。
原始缺失按字段统计：{"age": 27, "workclass": 184, "fnlwgt": 33, "education": 0, "education_num": 0, "marital_status": 0, "occupation": 184, "relationship": 0, "race": 0, "sex": 0, "capital_gain": 43, "capital_loss": 29, "hours_per_week": 28, "native_country": 51}

审计正向重放及完整字段/元数据/行序回滚通过，SHA256：775ca10e7963f5c4c66d48b89ce4d753afcb4e8965fdad5e703f93e3dac5ba13

## 输出文件
- cleaned.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\demo\cleaned.csv
- review.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\demo\review.csv
- detected_cells.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\demo\detected_cells.csv
- audit.jsonl：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\demo\audit.jsonl
- rolled_back.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\demo\rolled_back.csv
- repair_report.json：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\demo\repair_report.json
- repair_report.md：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\demo\repair_report.md
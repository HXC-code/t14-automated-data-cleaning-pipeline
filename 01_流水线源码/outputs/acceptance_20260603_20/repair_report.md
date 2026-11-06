# 数据清洗运行报告

运行：f8674416c1e14716808297bdb279ef7e；冻结V3.3-J；输入1600行、14预测字段，输出1600行。income不进入清洗输出。
自动净修改2094个单元；人工决定修改0个；待人工复核2426个；删除0行。耗时1.520秒。

|指标|处理前|处理后再次检测|
|---|---|---|
|missing_cells|742|742|
|detected_cells|4520|2466|
|numeric_type_or_range_alerts|886|222|
|format_alerts|698|0|
|spelling_alerts|732|0|
|unknown_category_alerts|21|21|
|unit_conversion_proposals|417|0|
|cross_field_alert_cells|933|1008|

以上是训练参考/规则告警，不是人工注入真值；合法长尾及语义例外可能保留。处理后扫描仅量化剩余问题，不执行第二轮自动修复。
原始缺失按字段统计：{"age": 63, "workclass": 185, "fnlwgt": 65, "education": 0, "education_num": 0, "marital_status": 0, "occupation": 185, "relationship": 0, "race": 0, "sex": 0, "capital_gain": 59, "capital_loss": 55, "hours_per_week": 72, "native_country": 58}

审计正向重放及完整字段/元数据/行序回滚通过，SHA256：ce744afdfd878f202e7793528643a16126a5068fe34a2c8128eb4936871c10d1

## 输出文件
- cleaned.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260603_20\cleaned.csv
- review.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260603_20\review.csv
- detected_cells.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260603_20\detected_cells.csv
- audit.jsonl：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260603_20\audit.jsonl
- rolled_back.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260603_20\rolled_back.csv
- repair_report.json：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260603_20\repair_report.json
- repair_report.md：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260603_20\repair_report.md
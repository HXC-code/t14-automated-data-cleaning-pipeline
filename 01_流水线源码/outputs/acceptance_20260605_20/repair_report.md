# 数据清洗运行报告

运行：172a4b9351bd4012957505cae04ec9eb；冻结V3.3-J；输入1600行、14预测字段，输出1600行。income不进入清洗输出。
自动净修改2114个单元；人工决定修改0个；待人工复核2189个；删除0行。耗时1.388秒。

|指标|处理前|处理后再次检测|
|---|---|---|
|missing_cells|746|746|
|detected_cells|4303|2204|
|numeric_type_or_range_alerts|885|213|
|format_alerts|710|0|
|spelling_alerts|732|0|
|unknown_category_alerts|18|18|
|unit_conversion_proposals|413|0|
|cross_field_alert_cells|894|961|

以上是训练参考/规则告警，不是人工注入真值；合法长尾及语义例外可能保留。处理后扫描仅量化剩余问题，不执行第二轮自动修复。
原始缺失按字段统计：{"age": 65, "workclass": 188, "fnlwgt": 67, "education": 0, "education_num": 0, "marital_status": 0, "occupation": 189, "relationship": 0, "race": 0, "sex": 0, "capital_gain": 64, "capital_loss": 60, "hours_per_week": 62, "native_country": 51}

审计正向重放及完整字段/元数据/行序回滚通过，SHA256：943992045038b8e2c8d25b8156ed8476931a35a6d72273c27fca1ef4e68ac4b5

## 输出文件
- cleaned.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260605_20\cleaned.csv
- review.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260605_20\review.csv
- detected_cells.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260605_20\detected_cells.csv
- audit.jsonl：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260605_20\audit.jsonl
- rolled_back.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260605_20\rolled_back.csv
- repair_report.json：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260605_20\repair_report.json
- repair_report.md：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260605_20\repair_report.md
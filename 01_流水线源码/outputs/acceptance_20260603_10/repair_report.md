# 数据清洗运行报告

运行：d4ec8b6222f44b39a4e7e04d6d3be9c2；冻结V3.3-J；输入1600行、14预测字段，输出1600行。income不进入清洗输出。
自动净修改1075个单元；人工决定修改0个；待人工复核1762个；删除0行。耗时1.228秒。

|指标|处理前|处理后再次检测|
|---|---|---|
|missing_cells|587|587|
|detected_cells|2837|1787|
|numeric_type_or_range_alerts|463|124|
|format_alerts|360|0|
|spelling_alerts|376|0|
|unknown_category_alerts|10|10|
|unit_conversion_proposals|231|0|
|cross_field_alert_cells|582|600|

以上是训练参考/规则告警，不是人工注入真值；合法长尾及语义例外可能保留。处理后扫描仅量化剩余问题，不执行第二轮自动修复。
原始缺失按字段统计：{"age": 42, "workclass": 185, "fnlwgt": 33, "education": 0, "education_num": 0, "marital_status": 0, "occupation": 185, "relationship": 0, "race": 0, "sex": 0, "capital_gain": 31, "capital_loss": 24, "hours_per_week": 29, "native_country": 58}

审计正向重放及完整字段/元数据/行序回滚通过，SHA256：e93d53272506bfe4213efdd4cbc25c86886c1f40ad9ab07e67fabe6f761bfbde

## 输出文件
- cleaned.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260603_10\cleaned.csv
- review.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260603_10\review.csv
- detected_cells.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260603_10\detected_cells.csv
- audit.jsonl：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260603_10\audit.jsonl
- rolled_back.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260603_10\rolled_back.csv
- repair_report.json：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260603_10\repair_report.json
- repair_report.md：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260603_10\repair_report.md
# 数据清洗运行报告

运行：848e12adb6b646a480854047e28eb615；冻结V3.3-J；输入1600行、14预测字段，输出1600行。income不进入清洗输出。
自动净修改330个单元；人工决定修改0个；待人工复核1148个；删除0行。耗时0.977秒。

|指标|处理前|处理后再次检测|
|---|---|---|
|missing_cells|476|476|
|detected_cells|1478|1152|
|numeric_type_or_range_alerts|146|43|
|format_alerts|112|0|
|spelling_alerts|115|0|
|unknown_category_alerts|6|6|
|unit_conversion_proposals|70|0|
|cross_field_alert_cells|195|197|

以上是训练参考/规则告警，不是人工注入真值；合法长尾及语义例外可能保留。处理后扫描仅量化剩余问题，不执行第二轮自动修复。
原始缺失按字段统计：{"age": 15, "workclass": 185, "fnlwgt": 9, "education": 0, "education_num": 0, "marital_status": 0, "occupation": 185, "relationship": 0, "race": 0, "sex": 0, "capital_gain": 11, "capital_loss": 7, "hours_per_week": 6, "native_country": 58}

审计正向重放及完整字段/元数据/行序回滚通过，SHA256：f6c7f834086b80a9b066e9f7d1d6af45e2a3c36600f6b516514e76396e5a6fd8

## 输出文件
- cleaned.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260603_3\cleaned.csv
- review.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260603_3\review.csv
- detected_cells.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260603_3\detected_cells.csv
- audit.jsonl：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260603_3\audit.jsonl
- rolled_back.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260603_3\rolled_back.csv
- repair_report.json：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260603_3\repair_report.json
- repair_report.md：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260603_3\repair_report.md
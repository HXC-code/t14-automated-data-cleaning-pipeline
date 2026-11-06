# 数据清洗运行报告

运行：205165666206471e98a9ed6d41714891；冻结V3.3-J；输入1600行、14预测字段，输出1600行。income不进入清洗输出。
自动净修改340个单元；人工决定修改0个；待人工复核879个；删除0行。耗时0.867秒。

|指标|处理前|处理后再次检测|
|---|---|---|
|missing_cells|476|476|
|detected_cells|1219|879|
|numeric_type_or_range_alerts|149|38|
|format_alerts|111|0|
|spelling_alerts|118|0|
|unknown_category_alerts|3|3|
|unit_conversion_proposals|72|0|
|cross_field_alert_cells|174|174|

以上是训练参考/规则告警，不是人工注入真值；合法长尾及语义例外可能保留。处理后扫描仅量化剩余问题，不执行第二轮自动修复。
原始缺失按字段统计：{"age": 10, "workclass": 188, "fnlwgt": 10, "education": 0, "education_num": 0, "marital_status": 0, "occupation": 189, "relationship": 0, "race": 0, "sex": 0, "capital_gain": 8, "capital_loss": 9, "hours_per_week": 11, "native_country": 51}

审计正向重放及完整字段/元数据/行序回滚通过，SHA256：d5c7a32fa814046f0f2659243a47563cf640f3ebf477cab7afdd3a0f8089b306

## 输出文件
- cleaned.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260605_3\cleaned.csv
- review.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260605_3\review.csv
- detected_cells.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260605_3\detected_cells.csv
- audit.jsonl：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260605_3\audit.jsonl
- rolled_back.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260605_3\rolled_back.csv
- repair_report.json：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260605_3\repair_report.json
- repair_report.md：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260605_3\repair_report.md
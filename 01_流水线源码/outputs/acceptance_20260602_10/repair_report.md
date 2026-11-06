# 数据清洗运行报告

运行：dfe7e3b37978437ab780dec9c86a2b25；冻结V3.3-J；输入1600行、14预测字段，输出1600行。income不进入清洗输出。
自动净修改1087个单元；人工决定修改0个；待人工复核1725个；删除0行。耗时1.162秒。

|指标|处理前|处理后再次检测|
|---|---|---|
|missing_cells|592|592|
|detected_cells|2812|1735|
|numeric_type_or_range_alerts|469|118|
|format_alerts|366|0|
|spelling_alerts|370|0|
|unknown_category_alerts|10|10|
|unit_conversion_proposals|219|0|
|cross_field_alert_cells|581|592|

以上是训练参考/规则告警，不是人工注入真值；合法长尾及语义例外可能保留。处理后扫描仅量化剩余问题，不执行第二轮自动修复。
原始缺失按字段统计：{"age": 30, "workclass": 191, "fnlwgt": 27, "education": 0, "education_num": 0, "marital_status": 0, "occupation": 191, "relationship": 0, "race": 0, "sex": 0, "capital_gain": 40, "capital_loss": 32, "hours_per_week": 28, "native_country": 53}

审计正向重放及完整字段/元数据/行序回滚通过，SHA256：ad2707398ac18821506dddd1bd6fd23a2efacbf2cbd01319f4785fa29a2a2c51

## 输出文件
- cleaned.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260602_10\cleaned.csv
- review.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260602_10\review.csv
- detected_cells.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260602_10\detected_cells.csv
- audit.jsonl：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260602_10\audit.jsonl
- rolled_back.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260602_10\rolled_back.csv
- repair_report.json：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260602_10\repair_report.json
- repair_report.md：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260602_10\repair_report.md
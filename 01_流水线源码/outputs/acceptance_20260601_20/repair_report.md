# 数据清洗运行报告

运行：5c016c3d742b4474abea6459a943a760；冻结V3.3-J；输入1600行、14预测字段，输出1600行。income不进入清洗输出。
自动净修改2081个单元；人工决定修改0个；待人工复核2138个；删除0行。耗时1.406秒。

|指标|处理前|处理后再次检测|
|---|---|---|
|missing_cells|736|736|
|detected_cells|4219|2151|
|numeric_type_or_range_alerts|849|208|
|format_alerts|710|0|
|spelling_alerts|730|0|
|unknown_category_alerts|19|19|
|unit_conversion_proposals|455|0|
|cross_field_alert_cells|906|986|

以上是训练参考/规则告警，不是人工注入真值；合法长尾及语义例外可能保留。处理后扫描仅量化剩余问题，不执行第二轮自动修复。
原始缺失按字段统计：{"age": 73, "workclass": 184, "fnlwgt": 62, "education": 0, "education_num": 0, "marital_status": 0, "occupation": 184, "relationship": 0, "race": 0, "sex": 0, "capital_gain": 53, "capital_loss": 57, "hours_per_week": 72, "native_country": 51}

审计正向重放及完整字段/元数据/行序回滚通过，SHA256：d4e9f44870468488c783364e3368ad6c5bf11c2c3dfa126242e4c1a32a5740b4

## 输出文件
- cleaned.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260601_20\cleaned.csv
- review.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260601_20\review.csv
- detected_cells.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260601_20\detected_cells.csv
- audit.jsonl：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260601_20\audit.jsonl
- rolled_back.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260601_20\rolled_back.csv
- repair_report.json：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260601_20\repair_report.json
- repair_report.md：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260601_20\repair_report.md
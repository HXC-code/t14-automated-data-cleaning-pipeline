# 数据清洗运行报告

运行：d76fc6ea2a504922883a0d4766a4ff34；冻结V3.3-J；输入1600行、14预测字段，输出1600行。income不进入清洗输出。
自动净修改348个单元；人工决定修改0个；待人工复核898个；删除0行。耗时0.853秒。

|指标|处理前|处理后再次检测|
|---|---|---|
|missing_cells|477|477|
|detected_cells|1246|901|
|numeric_type_or_range_alerts|159|37|
|format_alerts|114|0|
|spelling_alerts|112|0|
|unknown_category_alerts|4|4|
|unit_conversion_proposals|79|0|
|cross_field_alert_cells|198|201|

以上是训练参考/规则告警，不是人工注入真值；合法长尾及语义例外可能保留。处理后扫描仅量化剩余问题，不执行第二轮自动修复。
原始缺失按字段统计：{"age": 12, "workclass": 187, "fnlwgt": 9, "education": 0, "education_num": 0, "marital_status": 0, "occupation": 189, "relationship": 0, "race": 0, "sex": 0, "capital_gain": 11, "capital_loss": 7, "hours_per_week": 9, "native_country": 53}

审计正向重放及完整字段/元数据/行序回滚通过，SHA256：285c6b33f45a09e79e8944705cb6774f0f4b8a396dac712a25126564be68bf56

## 输出文件
- cleaned.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260604_3\cleaned.csv
- review.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260604_3\review.csv
- detected_cells.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260604_3\detected_cells.csv
- audit.jsonl：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260604_3\audit.jsonl
- rolled_back.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260604_3\rolled_back.csv
- repair_report.json：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260604_3\repair_report.json
- repair_report.md：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260604_3\repair_report.md
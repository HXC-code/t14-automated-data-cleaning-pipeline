# 数据清洗运行报告

运行：89340fcb7e3e4abc9acbd16d95facf4e；冻结V3.3-J；输入1600行、14预测字段，输出1600行。income不进入清洗输出。
自动净修改1083个单元；人工决定修改0个；待人工复核1537个；删除0行。耗时1.085秒。

|指标|处理前|处理后再次检测|
|---|---|---|
|missing_cells|586|586|
|detected_cells|2620|1541|
|numeric_type_or_range_alerts|457|124|
|format_alerts|381|0|
|spelling_alerts|369|0|
|unknown_category_alerts|13|13|
|unit_conversion_proposals|214|0|
|cross_field_alert_cells|562|595|

以上是训练参考/规则告警，不是人工注入真值；合法长尾及语义例外可能保留。处理后扫描仅量化剩余问题，不执行第二轮自动修复。
原始缺失按字段统计：{"age": 30, "workclass": 188, "fnlwgt": 39, "education": 0, "education_num": 0, "marital_status": 0, "occupation": 189, "relationship": 0, "race": 0, "sex": 0, "capital_gain": 29, "capital_loss": 30, "hours_per_week": 30, "native_country": 51}

审计正向重放及完整字段/元数据/行序回滚通过，SHA256：4f078ea0e429459bcff10befd9a942c33c7ff9381cbad4e714d1e1ff856c715a

## 输出文件
- cleaned.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260605_10\cleaned.csv
- review.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260605_10\review.csv
- detected_cells.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260605_10\detected_cells.csv
- audit.jsonl：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260605_10\audit.jsonl
- rolled_back.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260605_10\rolled_back.csv
- repair_report.json：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260605_10\repair_report.json
- repair_report.md：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260605_10\repair_report.md
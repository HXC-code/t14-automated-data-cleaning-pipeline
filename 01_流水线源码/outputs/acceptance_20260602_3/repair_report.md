# 数据清洗运行报告

运行：9e6e18f5b3894dc0acf126d191ff74bf；冻结V3.3-J；输入1600行、14预测字段，输出1600行。income不进入清洗输出。
自动净修改328个单元；人工决定修改0个；待人工复核1109个；删除0行。耗时0.931秒。

|指标|处理前|处理后再次检测|
|---|---|---|
|missing_cells|483|483|
|detected_cells|1437|1109|
|numeric_type_or_range_alerts|144|38|
|format_alerts|110|0|
|spelling_alerts|112|0|
|unknown_category_alerts|5|5|
|unit_conversion_proposals|68|0|
|cross_field_alert_cells|183|183|

以上是训练参考/规则告警，不是人工注入真值；合法长尾及语义例外可能保留。处理后扫描仅量化剩余问题，不执行第二轮自动修复。
原始缺失按字段统计：{"age": 9, "workclass": 191, "fnlwgt": 15, "education": 0, "education_num": 0, "marital_status": 0, "occupation": 191, "relationship": 0, "race": 0, "sex": 0, "capital_gain": 7, "capital_loss": 10, "hours_per_week": 7, "native_country": 53}

审计正向重放及完整字段/元数据/行序回滚通过，SHA256：a3b3f96a6a769c9fe4f0f333edd4ee4a3e32ae0e60af2887a8d7e46e130dd5f8

## 输出文件
- cleaned.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260602_3\cleaned.csv
- review.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260602_3\review.csv
- detected_cells.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260602_3\detected_cells.csv
- audit.jsonl：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260602_3\audit.jsonl
- rolled_back.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260602_3\rolled_back.csv
- repair_report.json：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260602_3\repair_report.json
- repair_report.md：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260602_3\repair_report.md
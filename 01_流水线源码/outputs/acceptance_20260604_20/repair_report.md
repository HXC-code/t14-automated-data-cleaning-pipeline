# 数据清洗运行报告

运行：867075444f00422ab3aa197245ed4a2c；冻结V3.3-J；输入1600行、14预测字段，输出1600行。income不进入清洗输出。
自动净修改2130个单元；人工决定修改0个；待人工复核2198个；删除0行。耗时1.395秒。

|指标|处理前|处理后再次检测|
|---|---|---|
|missing_cells|740|740|
|detected_cells|4327|2218|
|numeric_type_or_range_alerts|883|204|
|format_alerts|702|0|
|spelling_alerts|749|0|
|unknown_category_alerts|14|14|
|unit_conversion_proposals|437|0|
|cross_field_alert_cells|921|1001|

以上是训练参考/规则告警，不是人工注入真值；合法长尾及语义例外可能保留。处理后扫描仅量化剩余问题，不执行第二轮自动修复。
原始缺失按字段统计：{"age": 62, "workclass": 187, "fnlwgt": 63, "education": 0, "education_num": 0, "marital_status": 0, "occupation": 189, "relationship": 0, "race": 0, "sex": 0, "capital_gain": 62, "capital_loss": 58, "hours_per_week": 66, "native_country": 53}

审计正向重放及完整字段/元数据/行序回滚通过，SHA256：319c1fb60bd73019959ae6e82fd558f035619c36945c8496d415efe770093c1d

## 输出文件
- cleaned.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260604_20\cleaned.csv
- review.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260604_20\review.csv
- detected_cells.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260604_20\detected_cells.csv
- audit.jsonl：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260604_20\audit.jsonl
- rolled_back.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260604_20\rolled_back.csv
- repair_report.json：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260604_20\repair_report.json
- repair_report.md：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\acceptance_20260604_20\repair_report.md
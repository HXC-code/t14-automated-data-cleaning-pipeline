# 数据清洗运行报告

运行：fb1a56c388184cb09cba758a6560c7ec；冻结V3.3-J；输入4行、14预测字段，输出2行。income不进入清洗输出。
自动净修改3个单元；人工决定修改0个；待人工复核0个；删除2行。耗时0.355秒。

|指标|处理前|处理后再次检测|
|---|---|---|
|missing_cells|0|0|
|detected_cells|3|0|
|numeric_type_or_range_alerts|3|0|
|format_alerts|0|0|
|spelling_alerts|0|0|
|unknown_category_alerts|0|0|
|unit_conversion_proposals|3|0|
|cross_field_alert_cells|0|0|

以上是训练参考/规则告警，不是人工注入真值；合法长尾及语义例外可能保留。处理后扫描仅量化剩余问题，不执行第二轮自动修复。
原始缺失按字段统计：{"age": 0, "workclass": 0, "fnlwgt": 0, "education": 0, "education_num": 0, "marital_status": 0, "occupation": 0, "relationship": 0, "race": 0, "sex": 0, "capital_gain": 0, "capital_loss": 0, "hours_per_week": 0, "native_country": 0}

审计正向重放及完整字段/元数据/行序回滚通过，SHA256：1e961ac0691a0977cf3166e9be62f489f69f2c3da2a18f23487c7e8018a49d60

## 输出文件
- cleaned.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\deletion_validation\cleaned.csv
- review.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\deletion_validation\review.csv
- detected_cells.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\deletion_validation\detected_cells.csv
- audit.jsonl：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\deletion_validation\audit.jsonl
- rolled_back.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\deletion_validation\rolled_back.csv
- repair_report.json：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\deletion_validation\repair_report.json
- repair_report.md：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\deletion_validation\repair_report.md
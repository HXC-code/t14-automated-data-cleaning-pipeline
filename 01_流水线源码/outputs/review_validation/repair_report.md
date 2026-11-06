# 数据清洗运行报告

运行：dc1761eb007a49a19fd877adc8ea56ea；冻结V3.3-J；输入1行、14预测字段，输出1行。income不进入清洗输出。
自动净修改0个单元；人工决定修改1个；待人工复核0个；删除0行。耗时0.404秒。

|指标|处理前|处理后再次检测|
|---|---|---|
|missing_cells|1|0|
|detected_cells|1|0|
|numeric_type_or_range_alerts|0|0|
|format_alerts|0|0|
|spelling_alerts|0|0|
|unknown_category_alerts|0|0|
|unit_conversion_proposals|0|0|
|cross_field_alert_cells|0|0|

以上是训练参考/规则告警，不是人工注入真值；合法长尾及语义例外可能保留。处理后扫描仅量化剩余问题，不执行第二轮自动修复。
原始缺失按字段统计：{"age": 1, "workclass": 0, "fnlwgt": 0, "education": 0, "education_num": 0, "marital_status": 0, "occupation": 0, "relationship": 0, "race": 0, "sex": 0, "capital_gain": 0, "capital_loss": 0, "hours_per_week": 0, "native_country": 0}

审计正向重放及完整字段/元数据/行序回滚通过，SHA256：a40433f9fd232fff615c4374943d10db08471e80567664a4a2da924955fb4c42

## 输出文件
- cleaned.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\review_validation\cleaned.csv
- review.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\review_validation\review.csv
- detected_cells.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\review_validation\detected_cells.csv
- audit.jsonl：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\review_validation\audit.jsonl
- rolled_back.csv：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\review_validation\rolled_back.csv
- repair_report.json：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\review_validation\repair_report.json
- repair_report.md：D:\数据工程导论结课作业\V3_3_J_FINAL\outputs\review_validation\repair_report.md
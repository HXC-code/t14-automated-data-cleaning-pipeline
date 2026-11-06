# T14 自动化数据清洗流水线

这是一个面向 UCI Adult 表格数据的自动化清洗实验项目，最终版本为 V3.3-J。项目覆盖数据接入、质量画像、规则与统计检测、保守修复、人工复核、审计记录、回滚验证以及下游分类评估。

## 主要能力

- 14 个预测字段的读取、校验和画像
- 缺失值、量纲、拼写、格式、类别覆盖、数值异常及跨字段语义告警
- 自动修改与人工复核分离，修改前后值和规则依据写入审计日志
- 规范化内容 SHA256 校验与逆序回滚
- 固定五种子的五组 1,600 行配对实验
- 可重复的 206 项自动化测试

## 最终实验结果

正式冻结结果中，修复后相对未清洗数据的下游 F1 平均增益为：

| 目标噪声 | F1 平均增益 | 样本标准差 | 是否达到 3 pp |
|---|---:|---:|---|
| 3% | 4.0247608613 pp | 1.7141644821 pp | 是 |
| 10% | 2.8820421160 pp | 1.7245325510 pp | 否 |
| 20% | 3.3446632655 pp | 1.2321530278 pp | 是 |

10% 档未达到任务书要求，因此项目不能表述为最终性能验收全部通过。三档复用同一批 8,000 个测试身份，不能表述为 24,000 个不同样本。对已经评分的测试身份重新运行属于机械复现，不构成新的独立验收。

## 目录结构

| 目录 | 内容 |
|---|---|
| `01_流水线源码` | 主流水线、冻结策略、参考模型、配置和工具脚本 |
| `02_单元测试` | 单元测试源码、结果和运行日志 |
| `03_修复前后对比报告` | 修复质量、F1 验收、图表和最终报告 |
| `04_audit_log样例` | 审计日志、回滚和删除恢复样例 |
| `06_复现准备与运行说明` | 依赖锁定、复现脚本、Windows 快捷入口和说明 |

## 快速开始

目标环境为 Windows 64 位 Python 3.14。建议创建独立虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r "06_复现准备与运行说明\requirements-lock.txt"
```

对附带的 1,600 行示例数据运行清洗：

```powershell
Set-Location "01_流水线源码"
..\.venv\Scripts\python.exe -B run_pipeline.py `
  --input "examples\independent_dirty.csv" `
  --output "outputs\local_run"
```

运行完整测试：

```powershell
..\.venv\Scripts\python.exe -B run_tests.py
```

## F1 机械复现

从 [UCI Adult](https://archive.ics.uci.edu/dataset/2/adult) 获取 `adult.data` 和 `adult.test`，在仓库外的本地路径保存，然后运行：

```powershell
Set-Location "01_流水线源码"
..\.venv\Scripts\python.exe -B tools\reproduce_f1.py `
  --adult-train "path\to\adult.data" `
  --adult-test "path\to\adult.test" `
  --output "path\to\new_output_directory"
```

输出目录必须尚不存在。复现脚本不会导出测试标签，也不会重新调整超参数。

## 公开发布范围

为避免公开个人材料和本地数据副本，本仓库不包含：

- 原始 `05_原始数据（含标签，请勿公开）` 目录
- 研究生实训报告、个人姓名和学号相关内容
- 本地复现环境、运行输出和离线依赖 wheel 包

原始数据可从 UCI 官方页面获取。仓库中的聚合报告、测试结果、审计样例和模型工件来自公开的 Adult 数据集实验。

## 许可

本仓库未附单独的软件许可证。如需复用代码，请先联系仓库所有者确认授权。

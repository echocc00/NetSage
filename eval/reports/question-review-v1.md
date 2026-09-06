# NetAI-Bench 评测集复审报告 · v1

> 扫描 513 题 · 分层按 `source` 统计

## 总览
- schema 失败: **0**
- 深度检查命中: **109** 条（跨 3 类）
- 疑似近似重复: **0** 对真重复 + 200 对编号系列变体

| source | 数量 |
| auto_generated | 402 |
| template_derived | 81 |
| manual | 30 |

## 深度检查明细（按类别）
### root_causes<3（106）
- 来源分布: {'auto_generated': 106}
- 样本: [auto_generated] 仅 2 个, [auto_generated] 仅 2 个, [auto_generated] 仅 2 个, [auto_generated] 仅 2 个, [auto_generated] 仅 2 个, [auto_generated] 仅 2 个, [auto_generated] 仅 2 个, [auto_generated] 仅 2 个

### 文本残留占位（2）
- 来源分布: {'manual': 1, 'auto_generated': 1}
- 样本: [manual], [auto_generated]

### 标题示例/样例字样（1）
- 来源分布: {'manual': 1}
- 样本: [manual] 示例：OSPF 邻居反复震荡（VRP-8.180）

## 疑似近似重复（已区分系列变体）
- 真重复（同题复现，需合并/改题）: **0** 对
- 编号系列变体（`设计 … N/M` 规模梯度，属有意覆盖，非重复）: 200 对
无真重复。

## vendor×category 覆盖矩阵
| vendor | audit | config | design | perf | troubleshoot |
|---|---|---|---|---|---|
| huawei | 20 | 36 | 0 | 16 | 44 |
| cisco | 19 | 32 | 0 | 18 | 59 |
| h3c | 19 | 27 | 0 | 0 | 36 |
| juniper | 19 | 23 | 0 | 0 | 19 |
| arista | 3 | 26 | 0 | 0 | 11 |
| mellanox | 0 | 0 | 0 | 6 | 0 |

## 待人工复核优先级
按 source 分层：先 `manual`/`template_derived`（量少、专家证据链最可信），
再按批次复核 `auto_generated`。auto_generated 的 root_causes<3 与疑似重复优先。
# NetAI-Bench 评测报告 v1.0

> 生成日期：2026-08-24 · 评测集版本：v0.1.3（513 题）

## 1. 评测集统计

### 1.1 总量

| 指标 | 值 |
|---|---|
| 总题数 | 513 |
| schema 校验通过 | 513 / 513（100%） |
| 校验错误 | 0 |

### 1.2 类别分布

| 类别 | 数量 | 占比 |
|---|---|---|
| troubleshoot | 169 | 33% |
| config | 144 | 28% |
| design | 80 | 16% |
| audit | 80 | 16% |
| perf | 40 | 8% |

### 1.3 厂商分布

| 厂商 | 数量 | 占比 |
|---|---|---|
| cisco | 128 | 25% |
| huawei | 116 | 23% |
| h3c | 82 | 16% |
| cross | 80 | 16% |
| juniper | 61 | 12% |
| arista | 40 | 8% |
| mellanox | 6 | 1% |

### 1.4 难度分布

| 难度 | 数量 | 占比 |
|---|---|---|
| 2 | 147 | 29% |
| 3 | 162 | 32% |
| 4 | 162 | 32% |
| 5 | 42 | 8% |

### 1.5 协议覆盖（top 8）

| 协议 | 题数 |
|---|---|
| bgp | 82 |
| ospf | 65 |
| vxlan | 39 |
| interface | 31 |
| ipv6 | 18 |
| design/hld/bom | 80（design 类） |

## 2. 评测方法

### 2.1 RAG hit_rate

每题用 `input.symptom` 检索 RAG 知识库，检查 top-5 是否命中 `references.url`。
**目标：≥85%**（v2.0 19.2 验收 5）。

> 当前状态：评测题就绪，RAG 语料待 ingest 厂商手册。手册就绪后跑评测。

### 2.2 Agent 准确率

每题调对应 Agent，LLM-as-judge 按 `grading_rubric` 打分：
- must_have 命中率
- penalty 触发率（如"推荐重启设备"扣分）
- passed = must_have 全命中 + penalty=0

## 3. 引用

```bibtex
@misc{netsage2026,
  title={NetSage: AI Network Engineering Platform},
  author={NetSage Contributors},
  year={2026},
  url={https://github.com/echocc00/NetSage}
}
```

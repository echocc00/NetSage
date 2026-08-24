# NetAI-Bench · 网络工程 AI 评测基准

> NetSage 自研 benchmark：513 题，5 类 × 6 厂商，量化网络工程 AI 能力。
> 可引用于论文/博客作为基线对比。

## 评测集概览

| 维度 | 数量 | 覆盖 |
|---|---|---|
| 总题数 | 513 | — |
| troubleshoot | 169 | BGP/OSPF/VXLAN/VPN/接口/静态路由 |
| config | 144 | 5 厂商 × 7 协议 |
| design | 80 | Spine-Leaf/园区/双栈/RDMA Fabric |
| audit | 80 | CIS 基线 + ACL 分析 |
| perf | 40 | RDMA/RoCE/PFC/ECN |
| 厂商 | 6 | cisco 128 / huawei 116 / h3c 82 / juniper 61 / arista 40 / mellanox 6 |
| 难度 | 1-5 | 2 级 147 / 3 级 162 / 4 级 162 / 5 级 42 |

## 题目格式

每题一个 YAML 文件（`eval/dataset/NSG-Q-XXXX.yaml`），schema 见 `eval/runner/schema.py`。

```yaml
id: NSG-Q-0001
title: "OSPF 邻居反复震荡"
category: troubleshoot        # troubleshoot/config/design/audit/perf
vendor: huawei
difficulty: 3                 # 1-5
input:
  symptom: "OSPF-5-ADJCHG: Neighbor Down"
  evidence: [...]
expected_output:
  root_causes:                # troubleshoot/perf 类 ≥2
    - rank: 1
      cause: "..."
      verify: "show command"
      fix: "config"
anti_examples: ["..."]        # 错误回答
grading_rubric:
  must_have: [...]
  penalty: [...]
```

## 评测方法

### 1. RAG hit_rate（检索准确率）

每题用 `input.symptom` 检索 RAG，检查 top-5 是否命中 `references.url`。

```bash
python eval/runner/hit_rate.py
# 输出：hit_rate = 命中题数 / 总题数（目标 ≥85%）
```

### 2. Agent 能力评测（LLM-as-judge）

每题调对应 Agent（Troubleshooter/ConfigEngineer/SecurityAuditor/RdmAgent），对比 `expected_output` 打分。

```bash
python eval/runner/__init__.py
# 输出：准确率 / must_have 命中率 / penalty 触发率
```

### 3. 评分规则（grading_rubric）

| 项 | 说明 |
|---|---|
| must_have | 必须命中（每项 +1 分） |
| nice_to_have | 加分项（每项 +0.5） |
| penalty | 扣分项（每项 -2，如"推荐重启设备"） |
| passed | must_have 全命中 + penalty=0 |

## 引用

若你在论文/博客中引用 NetAI-Bench，请标注：

```bibtex
@misc{netsage2026,
  title={NetSage: AI Network Engineering Platform},
  author={NetSage Contributors},
  year={2026},
  url={https://github.com/echocc00/NetSage}
}
```

## 目录结构

```
eval/
├── dataset/          513 题 YAML（NSG-Q-0001 ~ NSG-Q-0519）
├── runner/
│   ├── __init__.py   评测 Runner（加载 + 打分 + 报告）
│   └── schema.py     题目 schema 校验器
└── reports/          评测报告
```

## 许可

评测集遵循仓库 Apache-2.0 许可。题目内容为 NetSage 团队原创 + 脱敏真实案例。

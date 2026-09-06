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

## 题目来源（source 溯源）

每题带 `source` 字段标注构造方式，引用时请按来源区分权重：

| source | 数量 | 含义 |
|---|---|---|
| `manual` | 30 | 人工逐题构造，证据链（日志/配置片段/计时器）经网络工程师审校 |
| `template_derived` | 81 | config 类，期望输出由 `backend/templates/` 下的 Jinja2 模板真实渲染得出 |
| `auto_generated` | 402 | 由参数化脚本批量生成（脚本见 `scripts/_build_archive/build_batch*.py`），故障模式与验证命令来自公开厂商文档，未逐题人工复核 |
| `customer_case` | 0 | 预留：脱敏真实客户案例 |

`auto_generated` 题目结构与 schema 一致、可用于回归与检索评测，但**不宜单独作为专家级能力的权威基线**；作横向对比时建议按 source 分层报告。

## 题目格式

每题一个 YAML 文件（`eval/dataset/NSG-Q-XXXX.yaml`），schema 见 `eval/runner/schema.py`。

```yaml
id: NSG-Q-0001
source: manual                # manual/template_derived/auto_generated/customer_case
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

每题用 `input.symptom + input.question` 检索 RAG，检查 top-5 是否命中 `references.url`。

```bash
cd backend && python scripts/eval_hit_rate.py
# 输出：hit_rate = 命中题数 / 总题数（目标 ≥85%）
```

**实测（2026-09-06，bge-m3 + 3 份华为手册 54 chunks）**：全量 174/513 = 33.9%，语料内 174/175 = 99.4%。
瓶颈是语料覆盖（上限 34.1%）而非检索算法，详见 [reports/hit_rate-v1.0.md](reports/hit_rate-v1.0.md)。

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

## 质量复审（v0.5.0 起）

`schema.py` 只保证结构可评测；`runner/review_dataset.py` 在其上做**深度质量扫描**并输出分层报告：

```bash
python eval/runner/review_dataset.py   # → eval/reports/question-review-v1.md
```

覆盖：root_causes 数量/概率越界/verify·fix 缺失、perf 缺 bottleneck、title 模板味、占位/乱码残留、
疑似重复（区分"编号系列变体" `设计 … N/M` 与真重复）、vendor×category 覆盖矩阵。
首轮结论（513 题）：schema 0 失败、**0 真重复**、200 对编号系列变体（规模梯度，属有意）。
106 题 troubleshoot 仅 2 根因已补齐到 3（513/513 schema 通过，root_causes<3 归零）。

## 目录结构

```
eval/
├── dataset/          513 题 YAML（NSG-Q-0001 ~ NSG-Q-0519）
├── runner/
│   ├── __init__.py   评测 Runner（加载 + 打分 + 报告）
│   ├── schema.py     题目 schema 校验器
│   └── review_dataset.py  深度质量复审（生成分层报告）
└── reports/          评测报告 + 复审报告
```

## 测试层级（统计口径）

仓库测试按三层口径记录，引用时须标明是哪个数字（防止"函数 vs 用例"虚标）：

| 口径 | 数量 | 来源 |
|---|---|:---|
| unit functions | 292 | `pytest tests/ --collect-only` 收集的去 parametrize 函数数 |
| unit cases | 501 | 单元测试 collected items（parametrize 展开后） |
| e2e scenarios | 18 | `tests/e2e/` 真实 HTTP 场景函数数 |

`backend/tests/conftest.py::test_inventory` 提供同一份当前数字供引用；数字变化时以 `pytest --collect-only -q` 实测为准。

## 许可

评测集遵循仓库 Apache-2.0 许可。题目按 `source` 字段标注构造方式：30 题人工构造、81 题模板渲染、402 题脚本批量生成（见"题目来源"章节）。

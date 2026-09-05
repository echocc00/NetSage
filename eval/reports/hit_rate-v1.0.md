# RAG hit_rate 实测报告（P7-7）

> 首次真实环境实测。此前 README 标注"hit_rate 待实测"，本报告给出可复现的实际数字。

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-09-06 |
| Postgres | 16-alpine + pgvector 0.8.0（本地构建 `netsage/pgvector:pg16`） |
| Embedder | **BAAI/bge-m3**（1024 维，真实模型，非 HashEmbedder） |
| 检索器 | `HybridRetriever`：向量（cosine/HNSW）+ BM25（tsvector）分数融合，top_k=5 |
| 语料 | `doc/vendor-manuals/huawei/` 3 份 VRP-8.180 手册（BGP/OSPF/VXLAN，543 行）→ **54 chunks** |
| 评测集 | 513 题（`eval/dataset/`），查询 = `input.symptom + input.question` |
| 命中判定 | top-5 中任一 chunk 的 `doc_id`/`source_url` 与题目 `expected_output.references.url` 的协议关键词匹配 |

## 结果

| 指标 | 数值 |
|---|---|
| **全量 hit_rate** | **174 / 513 = 33.9%** |
| 语料内可达题（references 指向 BGP/OSPF/VXLAN） | 175 |
| **语料内 hit_rate** | **174 / 175 = 99.4%** |
| 语料外误命中（应 miss 却判 hit） | 0 |
| 语料内漏检 | 1（NSG-Q-0013） |

## 解读

全量 33.9% 距 85% 目标的差距**不是检索算法问题，是语料覆盖问题**：

- 语料只有 BGP/OSPF/VXLAN 三个协议共 54 chunks，而 513 题的 references 覆盖 VPN/IPsec/无线/RoCE/InfiniBand/RFC 等 20+ 类目标。
- 语料能覆盖的 175 题里检索命中 174 题（99.4%），误命中 0 —— 说明混合检索 + 同义词改写在有语料时是有效的。
- 因此 **33.9% ≈ 175/513（34.1%，语料覆盖率上限）× 99.4%（检索精度）**。

### Embedder 对比

同一语料、同一评测集，仅切换 embedder：

| Embedder | 全量 hit_rate | 语料内 hit_rate |
|---|---|---|
| HashEmbedder（确定性 hash，无语义） | 28.8% | 84.6% |
| **bge-m3**（真实语义向量） | **33.9%** | **99.4%** |

语料内从 84.6% → 99.4%，证明真实 embedding 相比 mock 在语义召回上有实质提升（HashEmbedder 的 15% 漏检全部由 BM25 兜底失败导致）。

## 达标条件

要把全量 hit_rate 推到 ≥85%，需要的是**语料**而非调参：

| 缺口 | 需补语料 | 预计题数覆盖 |
|---|---|---|
| VPN/IPsec | 华为/思科 VPN 配置指南 | ~40 题 |
| 无线 | 华为 AirEngine / 思科 WLC 手册 | ~13 题 |
| RoCE/InfiniBand | 华为 CloudEngine RoCE 手册 + NVIDIA IB 文档 | ~40 题 |
| 多厂商 | 思科 IOS-XE / H3C Comware / Juniper Junos / Arista EOS | ~200 题 |
| RFC | RFC 2328/4271/4456/7296/7938 全文 | ~50 题 |

厂商手册受版权限制，`doc/vendor-manuals/` 已 gitignore，仅本地 ingest。RFC 为公开文档，可直接补入。

## 复现步骤

```bash
# 1. 构建带 pgvector 的 Postgres（pgvector/pgvector:pg16 官方镜像不可达时）
git clone --depth 1 --branch v0.8.0 https://github.com/pgvector/pgvector.git
cd pgvector && docker build -t netsage/pgvector:pg16 .   # 见下方 Dockerfile

# 2. 起库 + 迁移
docker run -d --name netsage-pg -e POSTGRES_USER=netsage \
  -e POSTGRES_PASSWORD=changeme_dev_only -e POSTGRES_DB=netsage \
  -p 5432:5432 netsage/pgvector:pg16
cd backend && python -m alembic upgrade head

# 3. ingest + 评测（HF_ENDPOINT 为国内镜像，可省略）
HF_ENDPOINT=https://hf-mirror.com python scripts/ingest_manuals.py
HF_ENDPOINT=https://hf-mirror.com python scripts/eval_hit_rate.py
```

pgvector 镜像 Dockerfile（Alpine 无 pg16 版 pgvector 包，需源码编译，跳过 LLVM JIT）：

```dockerfile
FROM postgres:16-alpine
COPY . /tmp/pgvector
RUN apk add --no-cache --virtual .build build-base postgresql16-dev \
 && cd /tmp/pgvector && make clean && make OPTFLAGS="" with_llvm=no \
 && make with_llvm=no install \
 && rm -rf /tmp/pgvector && apk del .build
```

详细逐题结果：`eval/reports/hit_rate.json`。

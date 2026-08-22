# NetSage · 开发计划与详细设计 v1.0

> 基线：`NetSage-最终技术方案-v2.0.md`（31 章 + 附录）
> 文档版本：v1.0 · 日期：2026-08-21
> 性质：工程实施文档——回答"怎么建"，不回答"建什么"（建什么见 v2.0）
> 覆盖：仓库结构、技术栈锁定、Phase 1 逐模块详细设计 + 逐周实现、Phase 2-4 模块设计、工程规范
> 原则对齐：**不降级**（全 scope 保留）、**MCP-First**、**三道闸**、**DeepSeek 为主 + 云端 API**

---

## 目录

- [Part I · 开发总览](#part-i--开发总览)
  - [一、仓库结构（Monorepo）](#一仓库结构monorepo)
  - [二、技术栈与版本锁定](#二技术栈与版本锁定)
  - [三、开发节奏与里程碑](#三开发节奏与里程碑)
  - [四、模块依赖关系图](#四模块依赖关系图)
- [Part II · Phase 1 详细设计](#part-ii--phase-1-详细设计)
  - [五、后端骨架（FastAPI）](#五后端骨架fastapi)
  - [六、数据模型与数据库设计](#六数据模型与数据库设计)
  - [七、Agent 运行时适配层](#七agent-运行时适配层)
  - [八、Agent 设计](#八agent-设计)
  - [九、MCP Server 设计](#九mcp-server-设计)
  - [十、设备接入层](#十设备接入层)
  - [十一、RAG 管线](#十一rag-管线)
  - [十二、数据脱敏模块](#十二数据脱敏模块)
  - [十三、三道闸与变更审批引擎](#十三三道闸与变更审批引擎)
  - [十四、前端骨架（React）](#十四前端骨架react)
  - [十五、CLI nsc](#十五cli-nsc)
  - [十六、W1-W2 超最小演示实现细节](#十六w1-w2-超最小演示实现细节)
  - [十七、测试策略落地](#十七测试策略落地)
- [Part III · Phase 2-4 模块设计](#part-iii--phase-2-4-模块设计)
  - [十八、Phase 2：NetBox / SUZIEQ / 多厂商 / 排障](#十八phase-2netbox--suzieq--多厂商--排障)
  - [十九、Phase 3：Nautobot / 安全 / 合规](#十九phase-3nautobot--安全--合规)
  - [二十、Phase 4：OpenSM / RdmAgent / 无线 / 多租户](#二十phase-4opensm--rdmagent--无线--多租户)
- [Part IV · 工程规范](#part-iv--工程规范)
  - [二十一、CI/CD 流水线](#二十一cicd-流水线)
  - [二十二、环境与配置管理](#二十二环境与配置管理)
  - [二十三、监控与可观测性接入](#二十三监控与可观测性接入)

---

# Part I · 开发总览

## 一、仓库结构（Monorepo）

```
netsage/
├── backend/                      # FastAPI 后端（Python 3.11+）
│   ├── app/
│   │   ├── main.py               # FastAPI 入口
│   │   ├── core/                 # 配置、安全、依赖注入
│   │   │   ├── config.py         # Settings (pydantic-settings)
│   │   │   ├── security.py       # JWT/OIDC + RBAC
│   │   │   ├── deps.py           # FastAPI Depends
│   │   │   └── logging.py        # 结构化 JSON 日志 + trace_id
│   │   ├── api/                  # REST 路由（按资源分文件）
│   │   │   ├── v1/
│   │   │   │   ├── devices.py
│   │   │   │   ├── projects.py
│   │   │   │   ├── designs.py
│   │   │   │   ├── changes.py    # 变更单 + 审批
│   │   │   │   ├── snapshots.py
│   │   │   │   ├── audit.py
│   │   │   │   └── agents.py     # Agent 会话 / SSE 流
│   │   │   └── ws.py             # WebSocket（DAG 执行进度）
│   │   ├── agents/               # Agent 定义（YAML 中间格式）
│   │   │   ├── definitions/
│   │   │   │   ├── planner.yaml
│   │   │   │   ├── config_engineer.yaml
│   │   │   │   └── validator.yaml
│   │   │   └── prompts/          # system prompt 模板
│   │   ├── runtime/              # agent_runtime 适配层
│   │   │   ├── base.py           # AgentDefinition + Backend 抽象
│   │   │   ├── langgraph_backend.py
│   │   │   └── runner.py         # 编译 + 执行 + HITL
│   │   ├── tools/                # MCP 客户端 + 工具注册
│   │   │   ├── mcp_client.py     # 统一 MCP 调用封装
│   │   │   └── registry.py       # 工具名 → MCP server 映射
│   │   ├── rag/                  # RAG 管线
│   │   │   ├── embedder.py       # bge-m3
│   │   │   ├── retriever.py      # 向量 + BM25 混合
│   │   │   ├── reranker.py       # bge-reranker
│   │   │   └── ingest.py         # 文档分块入库
│   │   ├── redact/               # 脱敏四层模型
│   │   │   ├── layer1_dict.py
│   │   │   ├── layer2_context.py
│   │   │   ├── layer3_router.py
│   │   │   └── mapping.py        # 可逆映射表（Redis）
│   │   ├── gates/                # 三道闸引擎
│   │   │   ├── simulation.py     # Containerlab 闸
│   │   │   ├── validation.py     # Batfish 闸
│   │   │   ├── approval.py       # 人审闸
│   │   │   └── pipeline.py       # 编排三闸
│   │   ├── access/               # 设备接入层
│   │   │   ├── base.py           # DeviceAdapter 抽象
│   │   │   ├── napalm_adapter.py
│   │   │   ├── netmiko_adapter.py
│   │   │   └── scrapli_adapter.py
│   │   ├── models/               # SQLAlchemy ORM
│   │   ├── schemas/              # Pydantic v2
│   │   ├── services/             # 业务逻辑（与 ORM 分离）
│   │   ├── workers/              # Celery 任务（仿真/下发等长任务）
│   │   └── audit/                # 审计日志 + 哈希链
│   ├── templates/                # Jinja2 配置模板库（见第二十七章）
│   ├── alembic/                  # 数据库迁移
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── e2e/
│   └── pyproject.toml
│
├── mcp-servers/                  # 每个 MCP server 独立包
│   ├── shared/                   # 共享工具（schema 校验、日志）
│   ├── containerlab-mcp/
│   ├── batfish-mcp/
│   ├── napalm-mcp/
│   └── README.md                 # 每个 server 的 schema 文档
│
├── frontend/                     # React 18 + Vite + AntD + React Flow
│   ├── src/
│   │   ├── api/                  # axios 封装 + SSE/WS
│   │   ├── components/
│   │   │   ├── editor/           # Monaco
│   │   │   ├── topology/         # React Flow
│   │   │   ├── terminal/         # xterm.js
│   │   │   └── chat/             # 侧栏 AI
│   │   ├── pages/
│   │   │   ├── devices/
│   │   │   ├── design/
│   │   │   ├── troubleshoot/
│   │   │   ├── changes/          # 审批工作台
│   │   │   └── audit/
│   │   ├── stores/               # zustand
│   │   └── routes/
│   └── package.json
│
├── cli/                          # nsc（typer）
│   ├── nsc/
│   │   ├── main.py
│   │   ├── commands/
│   │   └── client.py             # 调后端 API
│   └── pyproject.toml
│
├── eval/                         # NetAI-Bench
│   ├── dataset/                  # 题目 YAML
│   ├── runner/                   # 评测管线
│   └── reports/
│
├── infra/                        # 部署
│   ├── docker-compose.dev.yml    # 开发环境
│   ├── docker-compose.sim.yml    # Containerlab + Batfish 仿真环境
│   ├── k8s/                      # Helm charts
│   └── vault/                    # Vault 配置
│
├── docs/
└── .github/workflows/            # CI
```

**设计要点**：
- **backend 与 mcp-servers 分离**：MCP server 可独立部署（sidecar 或 K8s Deployment，见 v2.0 二十六章）。
- **agents/definitions 用 YAML 中间格式**：不绑定 LangGraph，符合 v2.0 第三十章可移植要求。
- **templates 独立目录 + GitOps**：模板库单独 PR review 流程（v2.0 二十七章）。

---

## 二、技术栈与版本锁定

| 层 | 组件 | 版本 | 锁定理由 |
|---|---|---|---|
| 后端框架 | FastAPI | 0.115+ | 异步 + Pydantic v2 |
| Python | CPython | 3.11 | async 性能 + match 语法 |
| ORM | SQLAlchemy | 2.0+ | async session |
| 迁移 | Alembic | 1.13+ | — |
| 校验 | Pydantic | v2 | 性能 |
| 任务队列 | Celery + Redis | 5.4+ | 仿真/下发长任务 |
| Agent 编排 | LangGraph | 0.2+（pin，封装在 runtime） | 状态机 |
| LLM 网关 | LiteLLM | 1.50+ | 多模型路由 |
| Embedding | bge-m3（本地 sentence-transformers） | 2.7+ | 多语言 |
| 向量库 | pgvector | 0.7+ | 与业务库合一 |
| 设备接入 | napalm / netmiko / scrapli | napalm 0.5+ / netmiko 4.4+ / scrapli 1.1+ | 多厂商 |
| 仿真 | Containerlab | 0.78+ | 声明式 YAML |
| 校验 | Batfish | 2024+ + pybatfish | 静态分析 |
| MCP SDK | mcp (FastMCP) | 1.0+ | 官方 Python SDK |
| 前端 | React 18 + Vite 5 | — | — |
| UI 库 | Ant Design 5 | — | 企业级 |
| 拓扑 | React Flow 12 | — | 节点图 |
| 编辑器 | Monaco Editor | — | 配置编辑 |
| 终端 | xterm.js | — | 终端面板 |
| 状态 | zustand | 5+ | 轻量 |
| CLI | typer | 0.12+ | — |
| 密钥 | HashiCorp Vault | 1.15+ | 凭证 |
| 审计 | PostgreSQL append-only + 哈希链 | — | 不可篡改 |
| 容器 | Docker + docker-compose（开发）/ K8s（生产） | — | — |
| 可观测 | OpenTelemetry + Prometheus + Loki + Grafana | — | — |

**版本锁策略**：所有依赖 `pyproject.toml` 用 `~=` 卡 minor，`poetry.lock` 提交；LangGraph 升级走 `agent_runtime` 适配层评审（v2.0 三十章 30.3）。

---

## 三、开发节奏与里程碑

对齐 v2.0 第三十一章 31.3，Phase 1（M1-M2）逐周展开：

| 周次 | 里程碑 | 主负责人 | 交付物 | 验收 |
|---|---|---|---|---|
| **W1** | 仓库初始化 + 后端骨架 + Docker 环境 | 后端 + SRE | Monorepo 骨架、FastAPI 起步、docker-compose.dev 跑通、PG/Redis/Vault 起来 | `curl /health` 200 |
| **W2** | 超最小演示（能跑 > 好看） | 全员 | nsc CLI + ConfigGen 单 Agent + Batfish 断言 + Containerlab 2 节点 BGP + report.md | demo 跑通 BGP peering 配置生成→仿真→断言 |
| **W3** | MCP Gateway + 3 MCP server | 后端 | containerlab-mcp / batfish-mcp / napalm-mcp | 3 server 工具调用测试通过 |
| **W4** | 脱敏 Layer1/3 + 审计日志 | 后端 | 脱敏过滤器 + 路由拦截器 + audit_logs 哈希链 | fuzz 1000 条无泄漏 |
| **W5** | LangGraph 适配层 + Planner/Validator Agent | AI 工程师 | agent_runtime + planner.yaml + validator.yaml | Plan-and-Execute 跑通 |
| **W6** | ConfigGen 完整 + 模板库首批 30 | AI + Tech Lead | config_engineer.yaml + cisco_iosxe/huawei_vrp OSPF/BGP 模板 | 生成配置通过 Batfish lint |
| **W7** | RAG 管线 + 评测集首批 50 题 | AI + 产品 | bge-m3 索引 + 混合检索 + 50 题评测集 | hit_rate ≥ 80% |
| **W8 (M1 末)** | DAG 联调 + LLM 网关难度路由 | AI + 后端 | Planner→ConfigGen→Validator DAG + LiteLLM 路由 | P95 < 30s |
| **W9-W10** | Web Console MVP | 前端 | 登录 + Chat + 设备管理 + 简易拓扑 + DAG 进度 | 3 人独立复现 |
| **W11** | 变更审批 + 配置快照/回滚 | 后端 | 三道闸 pipeline + 快照 + 审批工作台 | 端到端变更 + 回滚 demo |
| **W12 (M2 末)** | 端到端验收 + 文档 | 全员 | 12/12 验收达标（v2.0 十九章） | 12/12 PASS |

**关键 gate**：
- W2 末：超最小演示必须跑通——否则后续全部延期。
- W8 末：DAG P95 达标——否则 W9 起前端没东西可接。
- W12 末：12/12 验收——<9/12 启动 Phase 1.5（v2.0 19.3）。

---

## 四、模块依赖关系图

```
                    ┌──────────┐
                    │  CLI nsc │
                    └────┬─────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
   ┌─────────┐     ┌──────────┐    ┌──────────┐
   │ FastAPI │     │  Web UI  │    │  Agent   │
   │  网关   │◄────┤ (React)  │    │ Runtime  │
   └────┬────┘     └──────────┘    └────┬─────┘
        │                               │
        │          ┌────────────────────┼──────────┐
        │          ▼                    ▼          ▼
        │     ┌─────────┐         ┌─────────┐ ┌─────────┐
        │     │  RAG    │         │ MCP     │ │ LLM GW  │
        │     │ 管线    │         │ Client  │ │(LiteLLM)│
        │     └────┬────┘         └────┬────┘ └────┬────┘
        │          │                   │           │
        │     ┌────▼────┐         ┌─────▼─────┐    │
        │     │pgvector │         │ 3 MCP     │    │
        │     └─────────┘         │ servers   │    │
        │                         └─────┬─────┘    │
        │                               │          │
        │     ┌─────────────────────────┼──────────┘
        │     │                         │
        ▼     ▼                         ▼
   ┌──────────────┐              ┌──────────────┐
   │  PostgreSQL  │              │ 脱敏过滤器   │── 拦截所有 LLM/MCP 调用
   │ + audit_logs │              │ (4 层模型)   │
   └──────┬───────┘              └──────────────┘
          │
   ┌──────▼───────┐
   │ 三道闸引擎   │
   │ sim→val→appr │
   └──────┬───────┘
          │
   ┌──────▼───────┐
   │ 设备接入层   │
   │ NAPALM/...   │
   └──────────────┘
```

**依赖原则**：
- **Agent 只依赖 `agent_runtime` 接口 + `tools.registry`**，不直接 import MCP client / LangGraph。
- **所有出网调用（LLM / MCP / 设备）必经脱敏拦截器**（v2.0 二十章 Layer 3）。
- **写操作必经三道闸**（v2.0 十章），读操作宽松。

---

# Part II · Phase 1 详细设计

## 五、后端骨架（FastAPI）

### 5.1 应用入口结构

```python
# app/main.py（示意）
from fastapi import FastAPI
from app.core.config import settings
from app.core.logging import setup_logging
from app.api.v1 import api_router
from app.api.ws import ws_router

def create_app() -> FastAPI:
    app = FastAPI(title="NetSage", version="1.0", openapi_url="/openapi.json")
    setup_logging(app)
    app.include_router(api_router, prefix="/api/v1")
    app.include_router(ws_router)
    return app

app = create_app()
```

### 5.2 配置管理（pydantic-settings）

```python
# app/core/config.py（示意）
class Settings(BaseSettings):
    env: str = "dev"
    db_url: str
    redis_url: str
    vault_url: str | None
    # LLM
    litellm_master_key: str
    deepseek_api_key: str
    anthropic_api_key: str | None
    # MCP
    mcp_endpoints: dict[str, str]  # name -> url
    # 仿真
    containerlab_host: str         # 远程模式 SSH 跳板机
    batfish_host: str
    # 脱敏
    redact_blackbox_local_only: bool = True
    model_config = SettingsConfigDict(env_file=".env", env_nested_delimiter="__")
```

### 5.3 依赖注入

```python
# app/core/deps.py（示意）
async def get_db() -> AsyncSession: ...
async def get_current_user(token) -> User: ...
def require_role(min_role: Role):
    async def checker(user = Depends(get_current_user)): ...
    return checker
```

### 5.4 API 版本与路由约定

- 统一前缀 `/api/v1`。
- 响应信封：`{success: bool, data: T | null, error: str | null, meta: {trace_id, page?}}`（v2.0 patterns.md API Response Format）。
- SSE 流（`/api/v1/agents/sessions/{id}/stream`）：DAG 执行进度推送给前端。
- WebSocket（`/ws`）：终端面板双向交互。

### 5.5 异步模型

- **IO 密集（LLM/MCP/设备）全异步**：`async def`，httpx 异步客户端。
- **CPU 密集（Batfish JVM 交互、Containerlab 部署）走 Celery worker**：不阻塞事件循环。
- **DB session 每请求一个**，async sessionmaker。

---

## 六、数据模型与数据库设计

### 6.1 核心表（SQLAlchemy 2.0 声明式）

```python
# app/models/device.py
class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    vendor: Mapped[str]  # cisco / huawei / h3c / juniper / arista
    os: Mapped[str]      # iosxe / vrp / comware / junos / eos
    model: Mapped[str]
    version: Mapped[str]  # VRP-8.180 / 17.x
    mgmt_ip: Mapped[str]  # 脱敏前存储，访问时解密
    role: Mapped[str]     # spine/leaf/pe/ce/...
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    credential_id: Mapped[int] = mapped_column(ForeignKey("credentials.id"))
    # ...

# app/models/credential.py
class Credential(Base):
    __tablename__ = "credentials"
    id: Mapped[int] = mapped_column(primary_key=True)
    ref: Mapped[str]  # Vault path，如 "secret/netsage/device/42"
    type: Mapped[str]  # ssh / snmp / netconf
    # 不存明文，仅 Vault 引用（v2.0 八章）

# app/models/change.py
class ChangeRequest(Base):
    __tablename__ = "change_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int]
    intent: Mapped[dict] = mapped_column(JSON)  # NIM 片段
    status: Mapped[str]  # draft/sim_pending/val_pending/approval/deploying/done/failed/rolled_back
    created_by: Mapped[int]
    # 关联 steps / approvals / snapshot

class ChangeStep(Base):
    __tablename__ = "change_steps"
    id: Mapped[int]
    request_id: Mapped[int] = mapped_column(ForeignKey("change_requests.id"))
    seq: Mapped[int]            # 顺序
    device_id: Mapped[int]
    config_diff: Mapped[str]    # 渲染后的 diff
    rollback: Mapped[str]       # 回滚配置
    status: Mapped[str]

# app/models/snapshot.py
class ConfigSnapshot(Base):
    __tablename__ = "config_snapshots"
    id: Mapped[int]
    device_id: Mapped[int]
    change_request_id: Mapped[int | None]
    running_config: Mapped[str]  # 实际存 MinIO，这里存对象 key
    config_hash: Mapped[str]     # sha256
    created_at: Mapped[datetime]

# app/models/audit.py —— 不可篡改
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(server_default=func.now())
    user_id: Mapped[int | None]
    action: Mapped[str]        # read / write / approve / deploy / rollback
    resource_type: Mapped[str]
    resource_id: Mapped[str | None]
    before: Mapped[str | None]  # 脱敏后
    after: Mapped[str | None]
    prev_hash: Mapped[str]      # 上一条 id 的 hash
    self_hash: Mapped[str]      # sha256(prev_hash + payload)
    # INSERT ONLY：DB 层 REVOKE UPDATE/DELETE 权限
```

### 6.2 向量表

```sql
-- pgvector
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE kb_chunks (
    id BIGSERIAL PRIMARY KEY,
    doc_id VARCHAR(128),         -- 文档来源
    source_url TEXT,
    version VARCHAR(64),         -- VRP-8.180
    captured_at TIMESTAMP,
    chunk_text TEXT,
    embedding vector(1024),      -- bge-m3 dim=1024
    metadata JSONB,              -- 章节/标签
    tier INT,                    -- L1-L5
    bm25_tokens tsvector         -- GENERATED COLUMN for BM25
);
CREATE INDEX ON kb_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON kb_chunks USING gin (bm25_tokens);
```

### 6.3 迁移规范

- Alembic 自动生成 + 人工审校。
- 每次迁移含 `upgrade` + `downgrade`。
- `audit_logs` 表迁移后单独 REVOKE UPDATE/DELETE。

---

## 七、Agent 运行时适配层

### 7.1 抽象设计（v2.0 三十章落地）

```python
# app/runtime/base.py（示意）
@dataclass
class AgentDefinition:
    name: str
    role: str
    system_prompt: str
    tools: list[str]               # 工具名，引用 registry
    state_schema: dict             # JSON Schema
    transitions: list[Transition]  # DAG 描述
    interrupt_points: list[str]    # HITL 节点名

@dataclass
class Transition:
    from_node: str
    to_node: str
    condition: str | None           # 条件表达式

class AgentBackend(Protocol):
    def compile(self, defn: AgentDefinition) -> "CompiledGraph": ...
    # run / stream / interrupt / resume

class CompiledGraph(Protocol):
    async def invoke(self, state: dict, config) -> dict: ...
    async def stream(self, state: dict, config) -> AsyncIterator[dict]: ...
    async def interrupt_before(self, node: str, state) -> dict: ...
```

### 7.2 LangGraph 后端实现

```python
# app/runtime/langgraph_backend.py（示意）
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver

class LangGraphBackend(AgentBackend):
    def compile(self, defn: AgentDefinition) -> CompiledGraph:
        sg = StateGraph(defn.state_schema)
        for t in defn.transitions:
            sg.add_node(t.from_node, self._make_node(t.from_node, defn))
            sg.add_edge(t.from_node, t.to_node if t.to_node != "END" else END)
        checkpointer = PostgresSaver(...)  # 状态持久化，支持 HITL resume
        return sg.compile(
            interrupt_before=defn.interrupt_points or None,
            checkpointer=checkpointer,
        )
```

### 7.3 加载与执行

```python
# app/runtime/runner.py（示意）
class AgentRunner:
    def __init__(self, backend: AgentBackend, registry: ToolRegistry):
        self.backend = backend
        self.registry = registry

    def load(self, yaml_path: str) -> CompiledGraph:
        defn = AgentDefinition(**yaml.safe_load(yaml_path))
        return self.backend.compile(defn)

    async def run(self, graph, state, session_id):
        async for event in graph.stream(state, {"configurable": {"thread_id": session_id}}):
            yield event  # 推 SSE
```

### 7.4 YAML 中间格式示例

```yaml
# app/agents/definitions/config_engineer.yaml
name: config_engineer
role: "资深多厂商网络配置工程师"
system_prompt: !include prompts/config_engineer.md
tools:
  - mcp.napalm.get_facts
  - mcp.napalm.load_merge_candidate
  - template.render
  - rag.search
state_schema:
  type: object
  properties:
    intent: {type: object}
    device: {type: object}
    config_diff: {type: string}
    references: {type: array}
  required: [intent, device]
transitions:
  - {from: start, to: retrieve_context}
  - {from: retrieve_context, to: render}
  - {from: render, to: lint}
  - {from: lint, to: END}
interrupt_points: []   # ConfigGen 不中断，交给三道闸
```

**收益**：换框架时只改 `LangGraphBackend`，YAML 定义零改动。

---

## 八、Agent 设计

### 8.1 Planner（规划器）

- **职责**：意图分类 + DAG 规划 + 调度子 Agent。
- **输入**：用户自然语言 + 上下文（当前设备/VRF/最近告警）。
- **输出**：`Plan { intent, scenario, priority, steps: [{agent, input}] }`。
- **工具**：`rag.search`（检索同类案例）、`impact_analysis`（Phase 2）。
- **模式**：Plan-and-Execute。
- **Prompt 要点**："不得编造命令"、"必须引用来源"、"输出结构化 JSON"。

### 8.2 ConfigEngineer（配置工程师）

- **职责**：根据设计意图 + 设备型号/版本生成配置 diff + 回滚。
- **工具**：`template.render`（Jinja2）、`mcp.napalm.get_facts`、`rag.search`（命中厂商手册章节）。
- **流程**：retrieve_context → render（模板渲染）→ lint（语法自检）→ 输出 diff + rollback + references。
- **铁律**：**只渲染模板，不裸生成命令**（v2.0 十章"IR 只作翻译不作裸推理"）。
- **模板选择**：按 `vendor/os/version/protocol/feature` 匹配 templates 目录（第二十七章）。

### 8.3 Validator（校验器）

- **职责**：调用 Batfish + Containerlab 跑断言。
- **工具**：`mcp.batfish.assert_reachability`、`mcp.batfish.assert_acl`、`mcp.containerlab.deploy`、`mcp.containerlab.inspect`。
- **输出**：`ValidationReport { passed: bool, assertions: [...], evidence: [...] }`。
- **false negative = 0 要求**：Batfish 说通则真通（v2.0 19.1 验收 3）。

### 8.4 Agent 间上下文传递

- 通过 **NIM（Network Intent Model）** 实例在 state 中传递（v2.0 5.3）。
- state schema 包含 `nim: dict`，每步 Agent 读 NIM、写更新后的 NIM。
- checkpoint 存 PostgreSQL，支持中断恢复。

### 8.5 Prompt 工程规范

- 每个 Agent 的 system prompt 分段：角色 / 上下文 / 输出格式 / 约束 / few-shot。
- few-shot 预置 5-10 个典型案例（从 NetAI-Bench 抽，v2.0 二十二章）。
- Self-Consistency：关键结论（如根因排序）多次采样投票（指标 8）。

---

## 九、MCP Server 设计

### 9.1 通用架构（FastMCP）

```python
# mcp-servers/containerlab-mcp/server.py（示意）
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("containerlab-mcp")

@mcp.tool()
async def deploy_topology(topo_yaml: str, name: str) -> dict:
    """部署 containerlab 拓扑，返回节点状态。"""
    # 写临时文件 → ssh 到 containerlab_host → clab deploy
    ...

@mcp.tool()
async def destroy_topology(name: str) -> dict: ...

@mcp.tool()
async def inspect_topology(name: str) -> dict: ...

@mcp.tool()
async def save_topology(name: str) -> str:  # 保存为模板
    ...
```

### 9.2 三个 Phase 1 MCP Server 的工具清单

**containerlab-mcp**（8-10 人天）：
| 工具 | 输入 | 输出 |
|---|---|---|
| `deploy_topology` | topo_yaml, name | 节点列表 + 状态 |
| `destroy_topology` | name | ok/err |
| `inspect_topology` | name | 节点 + 链路 + 接口 |
| `save_topology` | name | 模板 id |
| `exec_on_node` | name, node, cmd | stdout（仿真内验证用） |

**batfish-mcp**（8-10 人天）：
| 工具 | 输入 | 输出 |
|---|---|---|
| `load_snapshot` | configs_dir | snapshot id |
| `assert_reachability` | snapshot, src, dst | pass/fail + 路径 |
| `assert_acl` | snapshot, acl_spec | pass/fail |
| `assert_routing` | snapshot, prefix | pass/fail + 路由表 |
| `lint_config` | config_text | 错误清单 |

**napalm-mcp**（6-8 人天）：
| 工具 | 输入 | 输出 |
|---|---|---|
| `get_facts` | device_id | 厂商/版本/接口 |
| `get_config` | device_id, source=running | 配置文本 |
| `load_merge_candidate` | device_id, config | candidate id |
| `compare_config` | device_id | diff |
| `commit` | device_id | ok |
| `discard` | device_id | ok |

### 9.3 MCP 客户端封装

```python
# app/tools/mcp_client.py（示意）
class MCPClient:
    def __init__(self, endpoints: dict[str, str]):
        self.conns = {name: Client(url) for name, url in endpoints.items()}

    async def call(self, tool_name: str, **kwargs):
        server, tool = tool_name.split(".", 1)  # "napalm.get_facts"
        return await self.conns[server].call_tool(tool, kwargs)

# app/tools/registry.py
class ToolRegistry:
    def __init__(self, mcp: MCPClient, redactor: Redactor):
        self.mcp = mcp
        self.redactor = redactor

    async def invoke(self, tool_name: str, **kwargs):
        # 1. 脱敏输入（Layer 1/2）
        kwargs = self.redactor.redact(kwargs)
        # 2. 调 MCP
        result = await self.mcp.call(tool_name, **kwargs)
        # 3. 还原输出占位符
        return self.redactor.restore(result)
```

### 9.4 部署模式

- 开发态：sidecar（docker-compose 同 compose 文件起 3 个 server）。
- 生产态：K8s Deployment + Service，独立扩缩容（v2.0 26.3）。
- 健康检查：`/health` 端点 → 指标 `mcp_server_uptime`（v2.0 23.3 指标 13）。

---

## 十、设备接入层

### 10.1 抽象接口

```python
# app/access/base.py（示意）
class DeviceAdapter(Protocol):
    async def get_facts(self, device: Device) -> DeviceFacts: ...
    async def get_config(self, device: Device, source: str) -> str: ...
    async def load_merge_candidate(self, device: Device, config: str) -> str: ...
    async def compare_config(self, device: Device) -> str: ...
    async def commit(self, device: Device) -> None: ...
    async def discard(self, device: Device) -> None: ...
    async def rollback(self, device: Device, snapshot: ConfigSnapshot) -> None: ...
```

### 10.2 三实现职责分工

| Adapter | 场景 | 理由 |
|---|---|---|
| **napalm_adapter** | 主路径（commit/rollback/diff） | 多厂商统一 API 最成熟 |
| **netmiko_adapter** | napalm 不支持的厂商/命令 | 灵活 CLI |
| **scrapli_adapter** | 高并发采集 | 异步性能好 |

**选择逻辑**：`AdapterFactory.create(device)` → 优先 napalm driver 是否支持该厂商 → 否则 netmiko → 大批量采集用 scrapli。

### 10.3 凭证注入

```python
# 设备连接前从 Vault 取凭证，不落明文
async def get_credential(cred_id: int) -> CredentialPayload:
    ref = await db.get_credential_ref(cred_id)
    return await vault.read(ref)  # 返回后立即用，不缓存明文
```

### 10.4 安全约束

- 所有设备连接走跳板机（Bastion）或专用管理网。
- SSH key 走 Vault，密码型凭证逐步淘汰。
- 读操作宽松（operator 可用），写操作（commit/rollback）必须经三道闸 + admin 审批。

---

## 十一、RAG 管线

### 11.1 文档入库（ingest）

```python
# app/rag/ingest.py（示意）
def chunk_manual(text: str, metadata: dict) -> list[Chunk]:
    # 四级分块：特性→场景→命令→注意事项，每块 ≤1500 token（v2.0 7.3）
    sections = split_by_heading(text, depth=4)
    chunks = []
    for s in sections:
        for piece in sliding_window(s, max_tokens=1500, overlap=100):
            chunks.append(Chunk(text=piece, metadata={**metadata, "path": s.path}))
    return chunks

async def embed_and_store(chunks: list[Chunk]):
    embs = await embedder.encode([c.text for c in chunks])  # bge-m3
    await db.bulk_insert_kb_chunks(chunks, embs)
```

### 11.2 混合检索

```python
# app/rag/retriever.py（示意）
async def hybrid_search(query: str, top_k: int = 50) -> list[Chunk]:
    # 1. 查询改写（同义词表）
    rewritten = rewrite_query(query)  # OSPF Neighbor ↔ Adjacency ↔ Peer
    # 2. 多路召回：原始 + 改写 + HyDE
    candidates = await asyncio.gather(
        vector_search(query, top_k),
        vector_search(rewritten, top_k),
        bm25_search(query, top_k),
        hyde_search(query, top_k),  # 让 LLM 生成假设答案再检索
    )
    merged = dedup(flatten(candidates))
    # 3. 重排序
    return await reranker.rerank(query, merged, top_n=top_k)
```

### 11.3 引用溯源

- 每个 chunk 带回 `source_url + version + captured_at`（v2.0 7.2）。
- Agent 输出时强制附带 references 字段。
- 评测指标 `rag_hit_rate`（v2.0 23.3 指标 9）。

### 11.4 Phase 1 范围

- 仅 1 厂商手册（华为 VRP 8.x 或 Cisco IOS-XE 17.x）。
- 100 题评测集 hit_rate ≥ 80%（v2.0 19.1 验收 8）。

---

## 十二、数据脱敏模块

### 12.1 模块结构（v2.0 二十章落地）

```python
# app/redact/layer1_dict.py（示意）
PATTERNS = {
    "IPV4": (r"\b\d{1,3}(\.\d{1,3}){3}\b", "[IPV4_{n}]"),
    "MAC":  (r"\b[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}\b", "[MAC_{n}]"),
    # ...（v2.0 20.2 全表）
}

class Layer1Redactor:
    def redact(self, text: str, mapping: MappingTable) -> str:
        for key, (pat, tpl) in PATTERNS.items():
            text, mapping = apply_regex(text, key, pat, tpl, mapping)
        return text, mapping

# app/redact/layer3_router.py
class Layer3Router:
    def route(self, content: Content) -> Route:
        tier = classify(content)  # 白/灰/黑
        if tier == "black" and settings.redact_blackbox_local_only:
            return Route(target="local_only")  # 禁止外发
        if tier == "grey":
            assert content.is_redacted  # 灰盒必须已脱敏
        return Route(target="cloud")
```

### 12.2 可逆映射

```python
# app/redact/mapping.py
class MappingTable:
    """每会话一个映射表，存 Redis，TTL 1h。"""
    def add(self, placeholder: str, original: str): ...
    def restore(self, text: str) -> str: ...  # 占位符还原
```

### 12.3 拦截器集成

```python
# 在 ToolRegistry.invoke 和 LLM 调用前统一拦截
class RedactingInterceptor:
    async def before_llm_call(self, messages: list, tier: str):
        messages = self.l1.redact_messages(messages)
        if tier == "black": raise BlackboxBlockError()
        return messages, mapping  # mapping 存 session
    async def after_llm_call(self, response: str, mapping):
        return mapping.restore(response)
```

### 12.4 对抗测试

- `eval/fuzz/` 目录 1000 条对抗样本。
- CI 周跑：发现泄漏即 fail（v2.0 20.5）。

---

## 十三、三道闸与变更审批引擎

### 13.1 状态机

```
draft
  │ ConfigEngineer 产出 diff
  ▼
sim_pending ──① Containerlab 仿真──▶ sim_passed / sim_failed
  │                                      │ 失败→回 ConfigEngineer 修正
  ▼                                      ▼
val_pending ──② Batfish 断言──▶ val_passed / val_failed
  │                                      │
  ▼                                      ▼
approval ──③ 人工逐条审批──▶ approved / rejected
  │                                      │ 拒绝→closed
  ▼
deploying ──DeployAgent 顺序下发──▶ done / failed
  │                                      │ 失败→自动 rollback
  ▼                                      ▼
done                                 rolled_back
```

### 13.2 Pipeline 实现

```python
# app/gates/pipeline.py（示意）
class GatePipeline:
    async def run(self, request: ChangeRequest):
        # 变更前快照
        await self.snapshot_all(request.devices)
        # 闸 1
        sim = await self.simulation_gate(request)
        if not sim.passed: return self.fail(request, sim)
        # 闸 2
        val = await self.validation_gate(request, sim.snapshot)
        if not val.passed: return self.fail(request, val)
        # 闸 3：人审（LangGraph interrupt_before）
        approved = await self.approval_gate(request)
        if not approved: return self.close(request, "rejected")
        # 下发
        await self.deploy(request)

    async def simulation_gate(self, req):
        topo = build_topology_from_nim(req.nim)
        deployed = await tools.invoke("containerlab.deploy_topology", topo)
        # 仿真内验证邻居/路由
        checks = await run_sim_checks(deployed)
        return GateResult(passed=all(checks), evidence=checks)

    async def validation_gate(self, req, snapshot):
        bf = await tools.invoke("batfish.load_snapshot", req.configs)
        results = []
        for assertion in req.assertions:  # reachability/ACL/routing
            results.append(await tools.invoke(f"batfish.assert_{assertion.type}", ...))
        return GateResult(passed=all(r.passed for r in results), evidence=results)

    async def approval_gate(self, req):
        # interrupt_before 节点，推 SSE 给前端审批工作台
        # admin 审批后 resume
        return await self.wait_for_approval(req.id)
```

### 13.3 配置快照与回滚

- 变更前：`napalm.get_config(running)` → 存 MinIO + hash 存 DB（v2.0 八章 ConfigSnapshot）。
- 下发失败：自动 `napalm.rollback(snapshot)` → 校验 hash 一致。
- 快照保留 7 天（v2.0 十章）。

### 13.4 RBAC 与审批

- `engineer` 可拟变更、发起审批；`admin` 可审批 + 回滚（v2.0 十章）。
- 审批工作台显示：diff、回滚预案、变更窗口、影响范围。
- 审批动作落 audit_logs（哈希链）。

---

## 十四、前端骨架（React）

### 14.1 页面结构

```
Layout（侧边栏导航）
├── 设备管理（devices/）        # 设备列表 + 详情 + 凭证
├── 设计工坊（design/）         # React Flow 拓扑画布 + Monaco 配置编辑 + 侧栏 AI
├── 排障工坊（troubleshoot/）   # 症状输入 + 证据面板 + 根因排序 + 修复建议
├── 变更审批（changes/）        # 审批工作台（diff + 回滚 + 影响范围）
├── 配置审计（audit/）          # 合规扫描 + 风险清单
├── 仿真中心（simulation/）     # Containerlab 拓扑 + 仿真日志
└── 系统设置（settings/）       # RBAC + 凭证 + 模板库
```

### 14.2 关键组件

- **MonacoEditor**：配置编辑 + diff 预览（monaco-editor + diff editor）。
- **ReactFlowCanvas**：拓扑可视化，节点点击看配置/状态；支持"AI 生成拓扑"指令。
- **TerminalPanel**：xterm.js，WebSocket 连后端，跳板机交互。
- **ChatSidebar**：侧栏 AI 对话，SSE 接 DAG 执行进度，展示 Agent 思考链 + 引用溯源。
- **DAGProgress**：可视化 Planner→ConfigGen→Validator 执行流。

### 14.3 状态管理

- **zustand** 全局 store：currentUser / currentProject / sessions。
- **React Query** 服务端状态（设备列表/变更单等）。
- **SSE EventSource** 接 `/api/v1/agents/sessions/{id}/stream`。

### 14.4 认证

- OIDC（Keycloak）→ JWT → axios 拦截器加 Authorization。
- 路由守卫按 RBAC 角色控制页面访问。

---

## 十五、CLI nsc

### 15.1 命令结构（typer）

```python
# cli/nsc/main.py（示意）
import typer
app = typer.Typer()

@app.command()
def ask(question: str):
    """自然语言提问：nsc ask "为什么 OSPF 邻居起不来" """

@app.command()
def simulate(topo: str):
    """跑仿真：nsc run simulate cml-topo.yaml"""

@app.command()
def generate(intent: str, device: str):
    """生成配置：nsc gen "BGP peering AS 65001" --device leaf01"""

@app.command()
def deploy(change_id: int):
    """下发变更（需审批）：nsc deploy 42"""
```

### 15.2 客户端

- 调后端 REST API（`httpx`）。
- 长任务（仿真/下发）接 SSE 流式输出到终端。
- 配置文件 `~/.nsc/config.yaml` 存后端地址 + token。

### 15.3 W1-W2 用途

- 超最小演示主要载体（v2.0 31.3 W1-W2）。
- 应急场景：跳板机内 `nsc ask` 快速排障（v2.0 十二章）。

---

## 十六、W1-W2 超最小演示实现细节

> 目标：2 周内跑通"能跑 > 好看"，验证技术可行性（v2.0 31.3 + 04-review 行动 1）。

### 16.1 目标场景

```
$ nsc gen "为上海-广州专线新建 BGP peering，AS 65001" --device leaf01 --vendor cisco
# ↓ ConfigEngineer Agent（单 Agent，无完整 DAG）
# ↓ DeepSeek API 生成 Cisco IOS-XE 配置 diff
# ↓ Validator 调 Batfish reachability 断言
# ↓ Containerlab 起 2 台 cXRd 仿真验证 BGP up
# ↓ 输出 report.md（含 diff + 断言结果 + 仿真日志）
```

### 16.2 最小组件清单

| 组件 | 实现 | 备注 |
|---|---|---|
| CLI | `cli/nsc` typer | 3 个命令：gen / simulate / report |
| Agent | 单个 ConfigEngineer（不走 LangGraph DAG，直接 LLM tool-use 循环） | W5 再升级到 DAG |
| LLM | LiteLLM + DeepSeek-V3 | 单一入口 |
| 校验 | Batfish Docker（`batfish/batfish` 镜像） | pybatfish 调用 |
| 仿真 | Containerlab + 2 台 cXRd | cXRd 镜像准备 |
| 报告 | Jinja2 渲染 Markdown | `report.md.j2` 模板 |

### 16.3 实现步骤（W1）

1. **D1-D2**：仓库初始化、docker-compose.dev（PG/Redis/Batfish/Containerlab 卷）、FastAPI `/health`。
2. **D3-D4**：CLI 骨架 + `nsc gen` 调 LiteLLM 生成配置（无模板，纯 LLM 先跑通）。
3. **D5**：Batfish MCP 雏形（`load_snapshot` + `assert_reachability`）。
4. **D6-D7**：Containerlab MCP 雏形（`deploy_topology` 2 节点 BGP）。

### 16.4 实现步骤（W2）

1. **D8-D9**：串起来——gen → batfish assert → containerlab deploy → 仿真内 `show bgp summary` 验证。
2. **D10**：Jinja2 report 模板，输出 `report.md`。
3. **D11**：端到端调试，准备 demo 数据集（3 个 BGP 场景）。
4. **D12-D14**：demo 录制 + 内部演示。

### 16.5 验收

- 3/3 BGP 场景跑通：配置生成 → Batfish 断言 pass → 仿真 BGP 邻居 Established → report.md 生成。
- 单次端到端 < 60s（W2 阶段，不卡 P95 30s，W8 DAG 优化后再卡）。

### 16.6 不做什么（边界）

- 不做 Web Console（W9 起）。
- 不做完整 DAG（W5 起）。
- 不做脱敏（W4 起，W2 暂用脱敏过的测试数据）。
- 不做审批流（W11 起）。
- 不做多厂商（W6 起）。

---

## 十七、测试策略落地

### 17.1 测试目录

```
backend/tests/
├── unit/           # 纯函数：脱敏正则、模板渲染、NIM 校验
├── integration/    # MCP server 调用、DB、Agent 链路（docker-compose 起）
└── e2e/            # 8 个关键场景（v2.0 24.3），用 Containerlab 仿真
```

### 17.2 覆盖率强制

- pytest-cov + pytest-asyncio。
- CI 阈值：单元 ≥80%，集成 ≥60%，E2E 关键场景 100%（v2.0 24.2）。
- 低于阈值 CI 阻断。

### 17.3 E2E 测试复用

- Containerlab 拓扑复用（同一 4 节点拓扑跑多个场景）。
- Batfish snapshot 复用（一次 load 多次 assert）。
- 目标：E2E 套件 < 5 分钟（v2.0 24.4）。

### 17.4 契约测试

- `schemathesis` 对 MCP server schema 跑 fuzz。
- 每次 MCP schema 变更触发。

### 17.5 性能基线（周跑）

- k6 脚本：50 并发 `/api/v1/agents/sessions`，P95 < 30s（v2.0 24.4）。

---

# Part III · Phase 2-4 模块设计

## 十八、Phase 2：NetBox / SUZIEQ / 多厂商 / 排障

### 18.1 NetBox 包装集成

- **SourceOfTruth 接口**（v2.0 三章）：
```python
class SourceOfTruth(Protocol):
    async def get_device(self, id) -> Device: ...
    async def get_topology(self, scope) -> Topology: ...
    async def get_ipam(self, scope) -> IPAM: ...
    async def write_change_record(self, record) -> None: ...
```
- `NetBoxAdapter`（REST + GraphQL）+ `NautobotAdapter`（Phase 3）双实现。
- NetBox v4 API 锁版本（v2.0 hermes-03 风险）。

### 18.2 SUZIEQ Poller 嵌入

- **ObserverAgent**：定时 poll 全网 → 标准化数据 → 喂 LLM 趋势分析。
- **Troubleshooter**：故障时调 `suzieq assert` 看状态变化。
- 凭证轮换：Vault + 定期 rotate（v2.0 17.4 隐藏成本）。

### 18.3 多厂商扩展

- 新增 NAPALM driver：H3C Comware / Juniper Junos / Arista EOS。
- 模板库扩展至 ~80（v2.0 27.4）。
- CI 矩阵测试：每厂商 × 每版本（v2.0 hermes-03 风险）。

### 18.4 Troubleshooter Agent

- **RCA 引擎**（v2.0 codex 设计）：
```
告警 → 拓扑定位 → 变更事件关联 → 流量基线偏离 → 协议状态机异常 → 因果图推理 → 根因排序
```
- 工具：`mcp.suzieq.assert`、`query_logs`、`query_flows`、`rag.search`。
- 输出：根因假设 + 证据链 + 验证步骤 + 修复命令。
- 案例 RAG：成功排障入库形成语料。

### 18.5 Phase 2 验收

- ≥3 厂商、≥3 排障闭环、RAG 500 题 hit_rate ≥85%（v2.0 19.2）。

---

## 十九、Phase 3：Nautobot / 安全 / 合规

### 19.1 Nautobot 深度集成

- `NautobotAdapter` 实现 SourceOfTruth。
- **自研 Nautobot App**：RDMA Fabric Manager 雏形（Phase 4 完整化）。
- GraphQL 原生查询（v2.0 hermes-03 优势③）。
- Job 系统：跑配置生成+验证流水线（v2.0 hermes-03 优势④）。

### 19.2 SecurityAuditor Agent

- 工具：`mcp.batfish.assert_acl`、CVE 库、`attack_surface_mapper`、`acl_auditor`。
- 检查项：peer 鉴权（MD5/AH）、GTSM、最大前缀、路由黑洞、管理面加固、VRF 隔离。
- 输出：风险清单 + 阻断式门禁（Critical 阻断 / Warning 警示）。
- **Phase 3 仅 Cisco + 华为**（v2.0 9.6 注）。

### 19.3 三道闸全量 + RBAC + SSO

- 完整审批流 + 快照回滚 + 四级 RBAC + OIDC（Keycloak）。
- 自动化率 ≥30%（v2.0 19.2）。

### 19.4 合规对照

- 等保 2.0 三权分立、日志 ≥6 个月（v2.0 11.2）。
- 安全合规白皮书输出（v2.0 11.3）。

---

## 二十、Phase 4：OpenSM / RdmAgent / 无线 / 多租户

### 20.1 OpenSM 容器化

- 基于 `jumanjihouse/docker-opensm`（v2.0 hermes-03）。
- **法务 memo 前置**（v2.0 二十一章）：M2 末法务签字后才编码。
- 隔离：subprocess / HTTP 调用，不链接不分发不修改（v2.0 21.3 三红线）。

### 20.2 RdmAgent（差异化护城河）

- **工具**：`mcp.opensm.*`（ibnetdiscover / iblinkinfo / perfquery）、rdma-core、perftest、ibdiagnet。
- **职责分离**（v2.0 9.5 注）：
  - 配置诊断：PFC/ECN/DCQCN 配置检查（Containerlab 可仿真）。
  - 性能验证：真实硬件 + perftest（Containerlab 不可仿真）。
- **M9 内部 Gate**：RdmAgent POC 跑通 1 场景（v2.0 19.2）。

### 20.3 WirelessAgent

- AP 布放 / 信道 / 漫游域 / 802.11k/v/r / 安全策略。
- 厂商 WLC API 适配。
- Phase 4 重要项，可延后 v1.1（v2.0 31.2）。

### 20.4 NetAI-Bench 对外发布

- 论文/博客发布（v2.0 22.5）。
- 差异化：RDMA/IB + 中文厂商 + 三道闸闭环评估。

### 20.5 多租户 + SSO

- per-tenant 隔离：SUZIEQ poller / NetBox 实例 / 审计日志 / LLM Token 计费（v2.0 04-review C③）。
- 企业版定价模型落地（v2.0 28.3）。

### 20.6 Helm/Operator 化

- K8s 生产部署：Helm chart + Operator。
- 私有化部署最小规格文档（v2.0 11.3）。

---

# Part IV · 工程规范

## 二十一、CI/CD 流水线

### 21.1 GitHub Actions 工作流

```yaml
# .github/workflows/ci.yml（示意）
jobs:
  lint:        # ruff + black + mypy
  unit-test:   # pytest unit, coverage ≥80%
  integration: # docker-compose 起 PG/Redis/MCP，pytest integration
  contract:    # schemathesis MCP schema
  e2e:         # Containerlab 8 场景（周跑/发版跑）
  security:    # OWASP ZAP + SQLMap（月跑）
```

### 21.2 分支策略

- `main`：受保护，PR only。
- `feat/*`：功能分支。
- `release/*`：发版分支。
- 模板库单独 `templates/*` 仓库或子目录，独立 PR review（v2.0 27.3）。

### 21.3 发布

- 语义版本：v1.0.0-beta.1。
- Helm chart 版本与 app 版本同步。
- 数据库迁移：发布前 Alembic upgrade + 回归测试。

---

## 二十二、环境与配置管理

### 22.1 三环境

| 环境 | 用途 | 部署 |
|---|---|---|
| dev | 本地开发 | docker-compose.dev |
| sim | 仿真测试 | docker-compose.sim（Containerlab + Batfish） |
| prod | 生产 | K8s + Helm |

### 22.2 配置分层

- `.env.dev` / `.env.prod`（不提交）。
- Vault 存所有密钥（DB 密码 / API key / 设备凭证）。
- pydantic-settings 启动时校验必填项（缺失即拒绝启动）。

### 22.3 密钥轮换

- LLM API key：每 90 天轮换。
- 设备 SSH key：每 30 天轮换（高敏感）。
- Vault 自动 rotate 策略。

---

## 二十三、监控与可观测性接入

### 23.1 指标采集

- **OTel Python SDK**：自动埋点 FastAPI + httpx + DB。
- **Prometheus**：抓取 18 个核心指标（v2.0 二十三章）。
- **Loki**：结构化 JSON 日志，trace_id 全链路。

### 23.2 仪表盘

- Grafana 4 个 dashboard：业务大盘 / Agent 视角 / 运维大盘 / SRE on-call（v2.0 23.5）。
- 告警：阈值超限 → 飞书/钉钉 webhook。

### 23.3 trace_id 链路

- 每请求生成 `trace_id`，贯穿 API → Agent → MCP → LLM → DB。
- audit_logs 带 trace_id，便于回溯。

### 23.4 MVP 先抓 10 指标

- dag_e2e_p95 / success_rate / daily_active_users / feedback_score / tool_failure_rate / token_per_request / rag_hit_rate / rag_retrieval_p95 / k8s_pod_restart_rate / queue_depth（v2.0 23.5）。

---

## 附录：Phase 1 任务拆解（对齐已有 TaskCreate）

| 任务 ID | 任务 | 对应章节 | 周次 |
|---|---|---|---|
| #1 | Phase 1: FastAPI 后端骨架 | 第五章 | W1 |
| #2 | Phase 1: 设备接入层 | 第十章 | W3-W4 |
| #3 | Phase 1: Agent 编排层 | 第七、八章 | W5-W8 |
| #4 | Phase 1: React 前端骨架 | 第十四章 | W9-W10 |
| #5 | Phase 1: 变更审批与闭环 | 第十三章 | W11 |

**补充任务（建议新增）**：
- MCP Server ×3（第九章）W3
- 数据脱敏模块（第十二章）W4
- RAG 管线 + 评测集（第十一、二十二章）W7
- CLI nsc + 超最小演示（第十五、十六章）W1-W2
- 三道闸引擎（第十三章）W11

---

## 变更日志

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v1.0 | 2026-08-21 | 首版开发计划与详细设计，覆盖目录结构、Phase 1 逐模块详细设计 + 逐周实现、Phase 2-4 模块设计、工程规范 | 架构组 |

---

> 本文档为 NetSage 工程实施基线，与 v2.0 技术方案配套使用。v2.0 回答"建什么"，本文档回答"怎么建"。

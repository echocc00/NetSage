# NetSage v1.0.2 规划 · 任务清单

> **目标**：收尾 v1.0.1 留下的 4 个 P0/P1 缺口（CLI nsc / frontend Dockerfile / mypy 真阻断 / 规划性文档），让"承诺 vs 实际"完全对齐  
> **时间窗口**：3 周（2026-09-07 ~ 2026-09-27）  
> **责任人**：@echocc00（单人维护；建议本周同步拉 1 个外部协作者提 PR 演练 CODEOWNERS）  
> **版本**：v1.0.2（patch · 修复版，不引入新功能）  
> **与 v1.0.1 关系**：v1.0.1 是审计修复，v1.0.2 是收尾修复

---

## 一、总览

### 1.1 本次要做的 7 件事

| # | 任务 | 文件 / 模块 | 周次 | 工作量 | 优先级 |
|---|---|---|---|:---:|:---:|
| 1 | CLI nsc 实现 | cli/nsc/ | W1 | 3 天 | 🔴 P0 |
| 2 | frontend Dockerfile + nginx | frontend/, infra/ | W1 | 2 天 | 🔴 P0 |
| 3 | mypy 转为真阻断 | .github/workflows/test.yml, backend/pyproject.toml | W2 | 1 天 | 🟡 P1 |
| 4 | 测试数声明透明化 | CHANGELOG.md, eval/README.md, backend/tests/conftest.py | W2 | 0.5 天 | 🟡 P1 |
| 5 | CHANGELOG + AGENTS.md | CHANGELOG.md, AGENTS.md (新增) | W2 | 1 天 | 🟡 P1 |
| 6 | gitignore 清理 | doc/ | W3 | 0.5 天 | 🟢 P2 |
| 7 | 拉 1 个外部 reviewer | .github/CODEOWNERS, GitHub | W3 | 异步 | 🔴 P0 |

### 1.2 不在本版（移到 v1.1 / v2.0）

- ❌ RAG 语料补全（需 NDA + 时间，移 v1.1 M2-M3）  
- ❌ RDMA 真实硬件验证（需 IB 测试床，移 v1.1 M1）  
- ❌ OIDC Keycloak E2E（需部署实例，移 v1.1 M1-M2）  
- ❌ Wireless WLC API 接入（需厂商凭据，移 v1.1 M2-M3）  
- ❌ 评测集 402 题人工复审（耗时长，移 v1.1 M1-M3）  
- ❌ 多租户 SaaS 化（架构改动大，移 v2.0）  

### 1.3 总投入估算

- **集中工作日**：~10 天
- **异步时间**：~7 天（拉 reviewer、CI 观察）
- **buffer**：3 天（修复 mypy 引入的新错 / 等 review）
- **总**：约 3 周

---

## 二、W1 详细计划（CLI nsc + frontend Dockerfile）

### 任务 1.1：CLI nsc 实现

**目标**：nsc 命令行可用，至少 5 个子命令  
**改动文件**：
- 新增：cli/nsc/__init__.py
- 新增：cli/nsc/main.py（typer app 主入口，~150 行）
- 新增：cli/nsc/api.py（httpx 异步客户端，~80 行）
- 新增：cli/nsc/commands/__init__.py
- 新增：cli/nsc/commands/ask.py（chat 命令，~50 行）
- 新增：cli/nsc/commands/run.py（触发 simulate / change 命令，~50 行）
- 新增：cli/nsc/commands/status.py（系统状态查询，~30 行）
- 新增：cli/nsc/commands/version.py（版本号，~20 行）
- 新增：cli/nsc/tests/test_main.py（~120 行，mock httpx）
- 修改：README.md（能力表 CLI nsc 改 ✅）

**依赖**：pyproject.toml 已声明 typer 0.12+ / httpx 0.27+ / rich 13+ / pydantic 2.7+，**无需新增依赖**。

**验收标准**：

1. pip install -e cli/nsc 后 nsc --help 显示 5 个子命令
2. nsc version 输出 NetSage v1.0.2
3. nsc status --url http://localhost:8000 返回 backend 健康 + 版本
4. nsc ask "OSPF 邻居为什么起不来" 返回 Markdown 报告（mock backend 也行）
5. nsc run simulate cml-topo.yaml --change-id CHG-001 触发 change 流程
6. pytest cli/nsc/tests/ 通过（≥ 20 测试函数）
7. CI 跑 cli/nsc 测试无错

**可能踩坑**：

- pyproject.toml 当前在 cli/nsc/pyproject.toml 里，但 backend 没引；CI 不会跑它的测试。**需要在 test.yml 加 cli 测试 job**（W3 一起做）
- typer 命令的 rich 输出在 CI 里可能被截断，加 --no-rich 选项兜底

**估算**：3 天

---

### 任务 1.2：frontend Dockerfile + nginx

**目标**：production docker-compose 真正能起前端服务  
**改动文件**：
- 新增：frontend/Dockerfile（multi-stage，~30 行）
- 新增：frontend/nginx.conf（SPA routing + reverse proxy，~25 行）
- 新增：frontend/.dockerignore
- 修改：infra/docker-compose.prod.yml（加 frontend service）
- 修改：infra/docker-compose.dev.yml（dev mode 加 frontend service，可选）
- 修改：README.md（5 分钟跑通段加前端服务启动说明）

**Dockerfile 关键设计**：

```dockerfile
# Build 阶段
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Runtime 阶段
FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD wget -qO- http://localhost:8080/health || exit 1
CMD ["nginx", "-g", "daemon off;"]
```

**nginx.conf 关键设计**：

- /api/v1/* 反代到 backend:8000
- /health 返回 200 纯静态
- SPA 路由 fallback 到 index.html
- gzip + cache headers

**验收标准**：

1. docker build -f frontend/Dockerfile -t netsage-frontend:v1.0.2 . 成功
2. 镜像大小 ≤ 80 MB（实测目标）
3. docker compose -f infra/docker-compose.prod.yml up -d 启动后 curl http://localhost:8080/health 返回 200
4. curl http://localhost:8080/ 返回 HTML 含 <title>NetSage
5. 浏览器访问 dashboard 能加载（手动验证）
6. CI 加 frontend 镜像 build job（可选；W3 一起做）

**风险**：

- 镜像 build 在国内可能因 npm 镜像慢超时，加 .npmrc 配 npmmirror（已有）
- nginx.conf 反代路径与 backend prefix（/api/v1）要对齐，避免 404

**估算**：2 天

---

## 三、W2 详细计划（mypy + 测试透明化 + AGENTS.md）

### 任务 2.1：mypy 真阻断

**目标**：CI 在 mypy 有错时红，未来不允许渐进式放纵  
**改动文件**：
- 修改：.github/workflows/test.yml（删 continue-on-error: true）
- 修改：backend/pyproject.toml（[tool.mypy] 段加严配置）

**mypy 严格化建议**：

```toml
[tool.mypy]
python_version = "3.12"
disallow_untyped_defs = true
disallow_incomplete_defs = true
warn_unused_ignores = true
warn_return_any = true
no_implicit_optional = true
check_untyped_defs = true
```

**前置工作**（必须先做）：

1. 本地跑 mypy backend/app --strict 看真实错误数
2. 评估工作量（预估 50-150 个 mypy 错要修）
3. 如果 > 200 个错，**拆 W2.5**：先修 critical 模块（gates/redact/audit），其他用 # type: ignore[xxx] 临时标注，分 3-4 周收敛

**验收标准**：

1. CI test.yml backend job 的 mypy step 没有 continue-on-error: true
2. 故意引入一个 mypy 错（例如删除一个 type hint），PR 应红
3. mypy 错数 ≤  20（剩余用 # type: ignore 标注的不算）

**估算**：1 天（不含前置工作量评估）

---

### 任务 2.2：测试数声明透明化

**目标**：CHANGELOG 区分"函数" vs "用例"，避免虚标嫌疑  
**改动文件**：
- 修改：CHANGELOG.md（v1.0.1 段测试数改写）
- 修改：eval/README.md（加测试层级说明）
- 修改：backend/tests/conftest.py（加 fixture）

**新写法示例**：

> 测试：283 unit functions（含 parametrize 展开 518 cases）+ 18 e2e scenarios（8 真实 HTTP 场景）通过；ruff 零告警

**conftest.py 新增**：

```python
@pytest.fixture(scope="session")
def test_inventory():
    """汇总测试层级，供 pytest --collect-only 调用方参考。"""
    return {
        "unit_functions": 283,
        "unit_cases_via_parametrize": 518,
        "e2e_scenarios": 18,
        "report": "pytest --collect-only -q | tail -3",
    }
```

**验收标准**：

1. CHANGELOG 文本明确说明 283 + 518 + 18 三档
2. 用户跑 pytest --collect-only -q 能看到两个数字
3. README 不再单独引用 518 单元测试

**估算**：0.5 天

---

### 任务 2.3：CHANGELOG Unreleased + AGENTS.md

**目标**：明确未来路径 + 建立 AI 协作规则  
**改动文件**：
- 修改：CHANGELOG.md（顶部加 [Unreleased] 段）
- 新增：AGENTS.md（项目级 AI 协作规则）

**Unreleased 段模板**：

```markdown
## [Unreleased]

### 计划 v1.0.2 (2026-09-27)
- CLI nsc 落地（5 命令）
- frontend Dockerfile + nginx
- mypy 真阻断
- 测试数透明化
- CHANGELOG Unreleased + AGENTS.md
- gitignore 清理
- 拉 1 个外部 reviewer
```

**AGENTS.md 应包含**：

```markdown
# NetSage 项目 AI 协作规则

## 编码风格
- ruff + mypy 严格模式（v1.0.2 后强制）
- 所有 PR 必须本地跑 ruff + mypy + pytest 通过
- 新功能必须带测试，单元测试覆盖率 ≥ 80%

## 测试要求
- 每 PR 添加/修改都需补测试
- 单元测试函数 + parametrize 展开数 + e2e 场景数 三层统计
- 不允许 vibe testing

## 文档约定
- CHANGELOG.md 必填，PR 不更新会被 CI 提示（手动）
- README 能力表 ✅/🟡 分级不可去除
- 诚实清单是核心约束

## 安全红线
- 任何密钥不进 git（.env.example 占位符 OK）
- LLM 调用必须经过 RedactingInterceptor
- 黑盒内容（running_config/credentials/raw_logs）禁止外发

## 仓库策略
- 单一维护者（@echocc00）期，邀请协作者加 CODEOWNERS
- 所有 PR 走 CODEOWNERS 流程
- scripts/_build_archive/ 是历史脚本，不再运行
```

**验收标准**：

1. CHANGELOG 顶部有 [Unreleased] 段
2. AGENTS.md 包含上述 5 个分类
3. AGENTS.md 与本会话的 AGENTS.md 一致（可对照）

**估算**：1 天

---

## 四、W3 详细计划（清理 + release）

### 任务 3.1：gitignore 清理

**目标**：删除工作树里的历史文件，让 clone 下来的人看不到这些中途产物  
**操作**：

1. git rm --cached doc/NetSage-遗留内容交付规范-v1.0.md
2. git rm --cached doc/NetSage-后续内容交付清单-v1.0.md
3. git rm --cached doc/NetSage-评测题出题指南-v1.0.md
4. rm -rf doc/templates-briefs/（gitignore 了但目录在）
5. 删 doc/vendor-manuals/ 空目录，或加 .gitkeep
6. .gitignore 加 __pycache__/ 兜底（避免遗留）

**验收标准**：

1. git ls-files doc/ 不再列 3 个中途文件
2. git status 干净
3. README 仓库结构段同步更新（如有提及）

**估算**：0.5 天

---

### 任务 3.2：拉 1 个外部 reviewer（异步）

**目标**：CODEOWNERS 不再单人  
**操作**：

1. 在项目 GitHub 上公开邀请协作者（README / Discussion / Twitter）
2. 优先找 1 个熟悉 FastAPI / LangGraph 的开发者 + 1 个网络协议背景的工程师
3. CODEOWNERS 加至少 1 个 handle
4. 演练 1 个简单 PR（修 typo / 加测试）走完整 review 流程

**验收标准**：

1. CODEOWNERS 有至少 2 个 handle
2. 1 个外部 PR 合并

**估算**：异步，1-2 周等回应

---

### 任务 3.3：v1.0.2 release 流程

**目标**：打 tag、生成 release notes  
**操作**：

1. 跑完整测试套件：pytest backend/tests -q + pytest cli/nsc/tests -q
2. ruff + mypy 双 0 告警
3. 更新 backend/app/core/config.py 的 version = "1.0.2"
4. 更新 CHANGELOG.md 顶部（把 Unreleased 移到 v1.0.2 段）
5. commit + push
6. 打 git tag -a v1.0.2 -m "v1.0.2 · 收尾补丁版"
7. release-drafter 自动起草 release notes
8. 检查 GitHub release 页面

**验收标准**：

1. v1.0.2 tag 在 GitHub
2. release notes 自动生成
3. README badge 自动更新为 v1.0.2

**估算**：0.5 天

---

## 五、Release Gate（v1.0.2 通过条件）

发布前必须 **全部 ✅**：

| # | 验收项 | 验证方式 |
|---|---|---|
| 1 | CLI nsc 5 命令可跑 | 手动 + 自动测试 |
| 2 | frontend Dockerfile 在 prod compose 起得来 | docker compose -f infra/docker-compose.prod.yml up -d |
| 3 | mypy 真阻断，PR 引入 mypy 错会红 | 故意引入 + 推 PR |
| 4 | CHANGELOG Unreleased + v1.0.2 段存在 | 文本检查 |
| 5 | AGENTS.md 提交 | 文件存在 |
| 6 | gitignore 清理完成 | git ls-files 检查 |
| 7 | 测试数：283 unit + ~20 cli + 18 e2e 通过 | pytest --collect-only |
| 8 | ruff + mypy 全 clean | CI green |
| 9 | CODEOWNERS 多 1-2 个 reviewer | 至少 1 个外部 PR 合并 |
| 10 | README 能力表 CLI nsc 改 ✅ | 文本检查 |

**任何一项不过 → 不打 tag**。

---

## 六、风险登记

| 风险 | 等级 | 缓解 |
|---|---|---|
| mypy 严格化引入 100+ 新错 | 🔴 高 | 先宽松模式跑通，再分批收紧；预留 1 周 buffer |
| 找不到外部 reviewer | 🟡 中 | 主动出击（GitHub / V2EX / 知乎），不靠等 |
| frontend Dockerfile 镜像 build 超时 | 🟢 低 | 国内 npm 镜像已配；缓存 docker layer |
| CLI 测试 mock 后端维护成本 | 🟢 低 | 用 respx 库拦截 httpx（pyproject 可加） |
| release-drafter 误生成 release notes | 🟢 低 | 手工 review GitHub release 再 publish |

---

## 七、与 v2.0 的边界

v1.0.2 是 **patch release**，**不做**：

- 多租户架构
- 真实 IB 硬件验证
- 真实 Keycloak 端到端
- 商业 license 实施
- 第三方安全审计

以上全部移到 **v2.0 路线图**（见 NetSage-v2.0-路线图-v1.0.md）。

v1.0.2 的使命是：**让 v1.0.1 留下的尾巴收干净，让 v2.0 从一个干净基线起步**。

---

## 附录 A：变更日志

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | 2026-09-06 | 初稿 |

> **下一步**：见 NetSage-v2.0-路线图-v1.0.md

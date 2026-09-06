# NetSage 项目 AI 协作规则

> 本文件定义 AI 协作开发 NetSage 时的行为准则。所有规则均为强制约束，违反会在 review 阶段被指出。

## 编码风格

- ruff + mypy 收敛严格模式（v0.4.2 后强制，见 [test.yml](.github/workflows/test.yml)）
- 所有 PR 必须本地跑过 `ruff check app tests` + `mypy app` + `pytest` 再提交
- 新功能必须带测试，单元测试覆盖关键路径 ≥ 80%
- FastAPI 用 `async def` + `Depends` 注入；不做阻塞 I/O 于 async 路由

## 测试要求

- 每个 PR 的添加/修改都必须补测试，不允许 "vibe testing"（只跑不改的裸提交）
- 测试数按三层统计，CHANGELOG 引用时须标明口径：
  - **unit functions**：`pytest --collect-only -q` 统计的收集函数数
  - **unit cases**：parametrize 展开后的实际用例数
  - **e2e scenarios**：`backend/tests/e2e/` 真实 HTTP 场景
- E2E 用 `TestClient` 跑真实链路，除非设备侧才 mock

## 文档约定

- `CHANGELOG.md` 必填：每个版本/PR 都记录，漏更会被 CI review 拒绝
- README 能力表 ✅/🟡 分级不可去除；🟡 = 代码就绪但外部条件未端到端验证
- "诚实清单"（已知限制表）是核心约束：承诺 vs 实际必须对齐，不允许只改文档不补代码

## 安全红线

- 任何密钥不进 git（`.env.example` 占位符可以，真实值禁止）
- LLM 调用必经 `RedactingInterceptor`；黑盒内容（running_config / raw_logs / credentials）禁止外发
- 变更下发命令只经模板引擎渲染 + 审批对象，禁止 LLM 裸发任意命令
- 脱敏开关保持开启，不要设 `REDACT_BLACKBOX_LOCAL_ONLY=false`

## 仓库策略

- 单一维护期（@echocc00）逐步邀请协作者，`CODEOWNERS` 保持 ≥ 2 handle
- 所有 PR 走 CODEOWNERS review 流程
- `scripts/_build_archive/` 是历史一次性脚本，不再运行；评测题/模板生成一律走规范文档
- 开发中途文档（规划/清单/手册原文）只本地保留，不入仓库（见 .gitignore）
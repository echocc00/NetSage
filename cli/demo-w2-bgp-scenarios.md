# W2 超最小演示 · 3 BGP 场景脚本（排障+生成+审计混合）

> 用户决策 2026-08-21：演示三场景 = BGP 邻居抖动排障 + eBGP peering 生成 + 路由策略黑洞检测审计
> 验收：3/3 场景跑通，端到端 < 60s（v2.0 开发计划十六章 16.5）

## 前置条件

1. 后端启动：`cd backend && uvicorn app.main:app --port 8000`
2. nsc 安装：`cd cli/nsc && pip install -e .`
3. （可选）cXRd 镜像 + LLM key 到位后启用真实仿真/生成

## 场景 1：BGP 邻居抖动排障（troubleshoot）

```bash
nsc ask "两台 Spine 间 BGP 邻居反复抖动，可能原因" --vendor huawei
```

**预期输出**：
- intent=troubleshoot, scenario=bgp, priority=high
- agent=troubleshooter
- approval=True（排障也可能触发变更，需人审）

## 场景 2：eBGP peering 配置生成（config）

```bash
nsc gen "为上海-广州专线新建 BGP peering，AS 65001" --vendor huawei --scenario bgp
```

**预期输出**：
- 会话创建 → ConfigEngineer 生成配置 diff
- Batfish lint pass
- 回滚配置生成
- 进三道闸审批流（requires_approval=True）

## 场景 3：路由策略黑洞检测审计（audit）

```bash
nsc ask "审计 200 台设备 BGP 配置是否有路由黑洞" --vendor huawei
```

**预期输出**：
- intent=audit, scenario=security, priority=high
- agent=security_auditor
- approval=True（审计结果可能阻断变更）

## 端到端验收

```bash
# 跑完三场景，检查：
# 1. 每个场景 intent/scenario 分类正确
# 2. 场景 2 生成配置含 "router bgp"
# 3. 场景 2 lint pass
# 4. 所有写操作 requires_approval=True（三道闸）

nsc health  # 后端就绪
# 依次跑三场景，统计 3/3 pass
```

## 未到位资源的影响

| 资源 | 未到位时 | 到位后 |
|---|---|---|
| cXRd 镜像 | simulate 命令提示待提供 | 真实 Containerlab 仿真 BGP up |
| LLM key | 配置用占位模板 | LLM 辅助参数填充 |
| 华为手册 | RAG 检索空 | 命中 VRP 手册章节 |

管线已跑通，资源到位即生效，无需改代码。

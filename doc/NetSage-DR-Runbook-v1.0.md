# NetSage · DR 容灾 Runbook v1.0

> Phase 4 M12 生产化，v2.0 二十五章。
> RPO=24h / RTO=2h · 文档版本 v1.0 · 日期 2026-08-24

## 1. 容灾目标

| 指标 | 目标 | 说明 |
|---|---|---|
| RPO | 24h | 每日备份，最多丢 24h 数据 |
| RTO | 2h | 故障到恢复 ≤2h |

## 2. 备份策略

### 2.1 备份内容

| 内容 | 方式 | 频率 | 保留 |
|---|---|---|---|
| PostgreSQL（业务数据） | `pg_dump` → gzip | 每日 02:00 | 30 天 |
| 模板库（86 模板） | tar.gz | 每日 | 90 天（变更少） |
| 评测题（513 题） | tar.gz | 每日 | 90 天 |
| .env.example + infra | tar.gz | 每周 | 90 天 |

### 2.2 备份脚本

```bash
# 每日备份（crontab）
0 2 * * * cd /opt/netsage && bash scripts/backup.sh >> /var/log/netsage-backup.log 2>&1
```

校验和：每次备份生成 sha256，恢复时校验完整性。

## 3. 恢复流程（RTO=2h）

### 3.1 故障检测

```bash
# 健康检查
curl http://localhost:8000/health
# 若 5xx 或超时 → 启动恢复
```

### 3.2 恢复步骤

```bash
# 1. 停服
docker compose -f infra/docker-compose.prod.yml down

# 2. 恢复 PG（需新 PG 实例）
docker compose -f infra/docker-compose.prod.yml up -d postgres

# 3. 恢复数据
bash scripts/restore.sh backups/netsage-YYYYMMDD-HHMMSS

# 4. 启动
docker compose -f infra/docker-compose.prod.yml up -d

# 5. 验证
curl http://localhost:8000/health
PYTHONIOENCODING=utf-8 python backend/scripts/phase4_acceptance.py
```

### 3.3 恢复验证清单

- [ ] /health 200
- [ ] 10 Agent 全注册
- [ ] 86 模板可加载
- [ ] 513 评测题 schema 通过
- [ ] 登录 + RBAC 正常

## 4. 演练计划

| 频率 | 内容 | 负责人 |
|---|---|---|
| 月度 | 备份 + 恢复演练（ staging） | SRE |
| 季度 | 全量 DR 演练（模拟主库故障） | SRE + Tech Lead |
| 年度 | 异地灾备演练 | SRE + 管理 |

## 5. 监控告警

- 备份失败 → 告警 SRE
- PG 连接异常 → /health 探测
- 审计哈希链断裂 → 告警（不可篡改校验）

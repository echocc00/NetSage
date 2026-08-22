# NetBox 部署（Phase 2 P2-2）

## 启动

```bash
# 首次：创建 netbox database + 起服务
docker exec netsage-pg psql -U netsage -d netsage -c "CREATE DATABASE netbox OWNER netsage;"

# 起 NetBox（可选 profile，不默认起）
docker compose -f infra/docker-compose.dev.yml -f infra/docker-compose.netbox.yml --profile netbox up -d netbox netbox-worker

# 等待就绪 + 初始化 token
bash infra/netbox/init.sh
```

## 配置

`backend/.env` 填入（init.sh 会输出 token）：
```
NETBOX_URL=http://localhost:8001
NETBOX_TOKEN=<init.sh 输出的 token>
```

## 访问

- NetBox Web UI: http://localhost:8001（admin / admin）
- NetBox API: http://localhost:8001/api/
- netbox-mcp: stdio 模式（`python mcp-servers/netbox-mcp/server.py`）

## 初始数据

启动后从 Phase 1 仿真设备导入：
```bash
python backend/scripts/seed_netbox.py
```
（脚本待 P2-2 收尾时实现）

## 注意

- NetBox 较重（~1GB RAM），默认不起（profile=netbox），按需启动
- 共用 Phase 1 的 PG（独立 database netbox）和 Redis
- 端口 8001（8000 被后端占用）
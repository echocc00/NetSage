#!/usr/bin/env bash
# NetBox 初始化脚本（首次启动后执行一次）
# 1. 创建 netbox database
# 2. 创建 admin token（供 NetBoxAdapter/netbox-mcp 用）
set -e

PG_CONTAINER="netsage-pg"
NETBOX_URL="http://localhost:8001"
NETBOX_ADMIN="admin"
NETBOX_ADMIN_PASSWORD="${NETBOX_ADMIN_PASSWORD:-admin}"

echo "=== 1. 创建 netbox database ==="
docker exec "$PG_CONTAINER" psql -U netsage -d netsage -c \
  "CREATE DATABASE netbox OWNER netsage;" 2>/dev/null || echo "netbox database 已存在，跳过"

echo "=== 2. 等待 NetBox 就绪 ==="
for i in $(seq 1 30); do
  if curl -sf "$NETBOX_URL/api/status/" >/dev/null 2>&1; then
    echo "NetBox 就绪（尝试 $i 次）"
    break
  fi
  sleep 5
done

echo "=== 3. 获取 API token ==="
TOKEN=$(curl -s -X POST "$NETBOX_URL/api/users/tokens/" \
  -H "Content-Type: application/json" \
  -u "$NETBOX_ADMIN:$NETBOX_ADMIN_PASSWORD" \
  -d '{"description": "netsage-dev"}' | python -c "import sys,json; print(json.load(sys.stdin).get('key',''))" 2>/dev/null || echo "")

if [ -z "$TOKEN" ]; then
  echo "⚠ 无法自动获取 token（可能已存在）。手动在 NetBox Web UI 创建。"
  echo "  访问 http://localhost:8001 → admin / $NETBOX_ADMIN_PASSWORD → API Tokens → 创建"
else
  echo "=== NetBox Token: $TOKEN ==="
  echo "填入 backend/.env:"
  echo "  NETBOX_URL=http://localhost:8001"
  echo "  NETBOX_TOKEN=$TOKEN"
fi

echo ""
echo "=== NetBox 初始化完成 ==="
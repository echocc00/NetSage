#!/usr/bin/env bash
# NetSage 备份脚本（Phase 4 M12 DR，v2.0 二十五章）。
#
# 备份内容：PostgreSQL（业务数据）+ 模板库 + 评测题 + 配置
# RPO=24h（每日备份），RTO=2h（恢复 runbook 见 doc/NetSage-DR-Runbook-v1.0.md）
#
# 用法：bash scripts/backup.sh [backup_dir]
# 恢复：bash scripts/restore.sh <backup_file>

set -euo pipefail

BACKUP_DIR="${1:-./backups}"
TS=$(date +%Y%m%d-%H%M%S)
DEST="${BACKUP_DIR}/netsage-${TS}"
mkdir -p "${DEST}"

echo "=== NetSage 备份 ${TS} ==="
echo "目标: ${DEST}"

# 1. PostgreSQL dump（需 PG 容器运行）
if command -v pg_dump >/dev/null 2>&1; then
  echo "[1/4] PostgreSQL dump..."
  pg_dump "${DATABASE_URL:-postgresql://netsage:netsage@localhost:5432/netsage}" \
    --no-owner --no-acl | gzip > "${DEST}/pg.sql.gz"
  echo "  ✓ pg.sql.gz"
elif docker ps --format '{{.Names}}' | grep -q netsage-postgres; then
  echo "[1/4] PostgreSQL dump (via docker)..."
  docker exec netsage-postgres pg_dump -U netsage netsage \
    --no-owner --no-acl | gzip > "${DEST}/pg.sql.gz"
  echo "  ✓ pg.sql.gz"
else
  echo "[1/4] PostgreSQL 跳过（无 pg_dump / 容器未运行）"
fi

# 2. 模板库
echo "[2/4] 模板库..."
if [ -d backend/templates ]; then
  tar czf "${DEST}/templates.tar.gz" backend/templates
  echo "  ✓ templates.tar.gz ($(find backend/templates -name '*.j2' | wc -l) 模板)"
fi

# 3. 评测题
echo "[3/4] 评测题..."
if [ -d eval/dataset ]; then
  tar czf "${DEST}/eval.tar.gz" eval/dataset
  echo "  ✓ eval.tar.gz ($(ls eval/dataset/*.yaml | wc -l) 题)"
fi

# 4. 配置 + .env.example
echo "[4/4] 配置..."
cp .env.example "${DEST}/" 2>/dev/null || true
cp -r infra "${DEST}/infra" 2>/dev/null || true
echo "  ✓ 配置"

# 校验
echo ""
echo "=== 备份完成 ==="
ls -lh "${DEST}/"
echo ""
echo "校验和: $(sha256sum ${DEST}/* | awk '{print $1}' | sha256sum | cut -c1-16)"
echo "恢复: bash scripts/restore.sh ${DEST}/netsage-${TS}.tar.gz"

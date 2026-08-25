#!/usr/bin/env bash
# NetSage 恢复脚本（Phase 4 M12 DR，v2.0 二十五章）。
# RTO=2h：恢复 PG + 模板 + 评测题，alembic 迁移，启动验证。
#
# 用法：bash scripts/restore.sh <backup_dir>

set -euo pipefail

BACKUP="${1:?用法: bash scripts/restore.sh <backup_dir>}"

if [ ! -d "${BACKUP}" ]; then
  echo "错误: 备份目录 ${BACKUP} 不存在"
  exit 1
fi

echo "=== NetSage 恢复 ${BACKUP} ==="

# 1. PostgreSQL
if [ -f "${BACKUP}/pg.sql.gz" ]; then
  echo "[1/4] PostgreSQL 恢复..."
  gunzip -c "${BACKUP}/pg.sql.gz" | \
    psql "${DATABASE_URL:-postgresql://netsage:netsage@localhost:5432/netsage}" 2>/dev/null || \
    docker exec -i netsage-postgres psql -U netsage netsage < <(gunzip -c "${BACKUP}/pg.sql.gz")
  echo "  ✓ PG 恢复"
fi

# 2. 模板
if [ -f "${BACKUP}/templates.tar.gz" ]; then
  echo "[2/4] 模板恢复..."
  tar xzf "${BACKUP}/templates.tar.gz"
  echo "  ✓ 模板"
fi

# 3. 评测题
if [ -f "${BACKUP}/eval.tar.gz" ]; then
  echo "[3/4] 评测题恢复..."
  tar xzf "${BACKUP}/eval.tar.gz"
  echo "  ✓ 评测题"
fi

# 4. 迁移 + 验证
echo "[4/4] Alembic 迁移 + 启动验证..."
cd backend
. .venv/Scripts/activate 2>/dev/null || true
alembic upgrade head
python -c "from app.main import app; print('import OK')"

echo ""
echo "=== 恢复完成 ==="
echo "下一步: uvicorn app.main:app --port 8000"
echo "验证: curl http://localhost:8000/health"

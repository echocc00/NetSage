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

# 0. 完整性校验（backup.sh 生成的 SHA256SUMS；旧版备份无清单则提示跳过）
if [ -s "${BACKUP}/SHA256SUMS" ]; then
  echo "[0/4] SHA256SUMS 校验..."
  ( cd "${BACKUP}" && sha256sum -c SHA256SUMS --quiet ) \
    || { echo "错误: 校验失败，备份可能损坏，已中止恢复"; exit 1; }
  echo "  ✓ 校验通过"
else
  echo "[0/4] 无 SHA256SUMS 清单（旧版备份），跳过校验"
fi

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
# venv 位置自动探测：Windows（Scripts/）与 Linux/macOS（bin/）都试
if [ -f .venv/Scripts/activate ]; then
  . .venv/Scripts/activate
elif [ -f .venv/bin/activate ]; then
  . .venv/bin/activate
else
  echo "  注意: 未找到 backend/.venv，沿用当前 PATH 的 python/alembic"
fi
alembic upgrade head
python -c "from app.main import app; print('import OK')"

echo ""
echo "=== 恢复完成 ==="
echo "下一步: uvicorn app.main:app --port 8000"
echo "验证: curl http://localhost:8000/health"

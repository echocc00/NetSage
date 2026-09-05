# 历史构建脚本（归档）

这些脚本是 v0.1.x 评测题与模板的**一次性生成/修复脚本**，用于批量构建 513 道评测题和 86 个配置模板。
**历史产物，不再运行**，仅保留作为审计追溯与生成方法参考。

## 内容

- `build_batch*_*.py` — 评测题批量生成（513 题，分 9 批）
- `build_003*.py` — 单题修复
- `fix_*.py` — YAML 格式修复（缩进/rubric/schema 校正）
- `lift_rubric.py` — grading_rubric 提升规范化
- `render_*smoke*.py` — 模板冒烟测试

## 当前运维脚本

仓库根 `scripts/` 只保留持续运维脚本：
- `backup.sh` — DR 备份（PG dump + 模板 + 评测题）
- `restore.sh` — DR 恢复

后端 `backend/scripts/` 保留：
- `eval_hit_rate.py` — RAG hit_rate 评测
- `ingest_manuals.py` — 厂商手册 ingest
- `phase*_acceptance.py` — 各阶段验收
- `seed_netbox.py` — NetBox 种子数据

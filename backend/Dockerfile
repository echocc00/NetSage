# NetSage 后端生产镜像
# 多阶段：builder 只装第三方依赖（层缓存友好，改源码不重装依赖）→ runtime 装源码包并以非 root 运行
# 用法：docker build -f backend/Dockerfile -t netsage-backend:v0.1.0 backend
# 注意：生产镜像只装运行期依赖（不带 [dev] extras，tests/ 已被 .dockerignore 排除）

# ---- 构建阶段：装依赖 ----
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 依赖装进独立 venv（不用 pip --user：产物在 /root/.local 下，非 root 运行用户读不到）
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

# 只拷 pyproject.toml 先装依赖（非 editable）：源码未拷入，包本体是空壳，
# 目的仅是把第三方依赖固定进带缓存的层；runtime 阶段再装真实源码包
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# ---- 运行阶段 ----
FROM python:3.12-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# 非 root 运行用户（uid 1001）
RUN adduser --system --uid 1001 netsage

COPY --from=builder /opt/venv /opt/venv

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 源码包在此阶段安装（依赖已就位，--no-deps 免二次解析）；
# --chown 保证 alembic/、templates/、app/ 对 netsage 用户可读（迁移与模板渲染不落盘，无需可写）
COPY --chown=netsage:root . .
RUN pip install --no-cache-dir --no-deps .

USER netsage

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "4", "--proxy-headers", "--forwarded-allow-ips=*"]

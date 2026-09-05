# 本地构建 pgvector（官方 pgvector/pgvector:pg16 拉取失败时的兜底）
#
# 用法：
#   git clone --depth 1 --branch v0.8.0 https://github.com/pgvector/pgvector.git /tmp/pgvector
#   cp infra/pgvector/Dockerfile /tmp/pgvector/
#   docker build -t netsage/pgvector:pg16 /tmp/pgvector
#   # 然后把 docker-compose.dev.yml 的 image 改为 netsage/pgvector:pg16
#
# 说明：Alpine 仓库的 postgresql-pgvector 只跟 pg18，与 postgres:16-alpine 不匹配，
# 故源码编译。with_llvm=no 跳过 JIT bitcode（Alpine 无匹配 clang/llvm 版本）。
FROM postgres:16-alpine
COPY . /tmp/pgvector
RUN apk add --no-cache --virtual .build build-base postgresql16-dev \
 && cd /tmp/pgvector && make clean && make OPTFLAGS="" with_llvm=no \
 && make with_llvm=no install \
 && rm -rf /tmp/pgvector && apk del .build

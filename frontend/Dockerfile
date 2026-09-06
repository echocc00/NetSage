# NetSage 前端生产镜像（v0.4.2）
# 多阶段：node:20-alpine 构建 → nginx:1.27-alpine 运行（端口 80）
# 用法：docker build -f frontend/Dockerfile -t netsage-frontend:v0.4.2 .

# ---- Build 阶段 ----
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# ---- Runtime 阶段 ----
FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/health || exit 1
CMD ["nginx", "-g", "daemon off;"]
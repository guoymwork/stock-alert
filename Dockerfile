# ============================================================
# 构建参数：默认走官方源；网络受限时可在 .env 中覆盖（见 .env.example）
# ============================================================
ARG NODE_IMAGE=node:20-bookworm-slim
ARG PYTHON_IMAGE=python:3.11-slim

# ============================================================
# Stage 1: 构建前端静态资源
# ============================================================
FROM ${NODE_IMAGE} AS frontend-build

# 保持 frontend/ 这一层目录，vite 的 outDir（../backend/static）才能解析到 /build/backend/static
WORKDIR /build/frontend

ARG NPM_REGISTRY=""

COPY frontend/package.json frontend/package-lock.json ./
RUN if [ -n "$NPM_REGISTRY" ]; then \
        npm config set registry "$NPM_REGISTRY" && npm config set replace-registry-host always; \
    fi \
    && npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build


# ============================================================
# Stage 2: Python 运行时（同时托管 API 与前端静态页）
# ============================================================
FROM ${PYTHON_IMAGE} AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai \
    STOCK_ALERT_DB_PATH=/app/data/stock.db

# date.today() 用于分时数据时间戳，容器内必须是东八区
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && ln -snf /usr/share/zoneinfo/${TZ} /etc/localtime \
    && echo ${TZ} > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ARG PIP_INDEX_URL=""
COPY backend/requirements.txt ./requirements.txt
RUN if [ -n "$PIP_INDEX_URL" ]; then \
        pip install --no-cache-dir -i "$PIP_INDEX_URL" -r requirements.txt; \
    else \
        pip install --no-cache-dir -r requirements.txt; \
    fi

# backend/app -> /app/app ：config.py 里 BASE_DIR 会解析成 /app，
# 因此 DATA_DIR=/app/data、STATIC_DIR=/app/static，路径自然对齐
COPY backend/app ./app
COPY --from=frontend-build /build/backend/static ./static
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh && mkdir -p /app/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

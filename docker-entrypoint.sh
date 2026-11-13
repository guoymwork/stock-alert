#!/bin/sh
# 容器启动前准备：确保 SQLite 数据目录存在
set -e

DB_PATH="${STOCK_ALERT_DB_PATH:-/app/data/stock.db}"
DB_DIR="$(dirname "$DB_PATH")"

mkdir -p "$DB_DIR"
echo "[entrypoint] 数据目录就绪: $DB_DIR"

exec "$@"

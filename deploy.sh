#!/usr/bin/env bash
# 从 GitHub 拉取最新代码并重建、重启容器（在部署机上运行）
set -euo pipefail

cd "$(dirname "$0")"

echo "[1/3] 拉取最新代码..."
# 显式 fetch + merge，不依赖本地分支的 upstream 配置
git fetch origin main
git merge --ff-only origin/main

echo "[2/3] 重建并启动..."
if docker info >/dev/null 2>&1; then
  DC=(docker compose)
else
  DC=(sudo docker compose)
fi
"${DC[@]}" up -d --build

echo "[3/3] 当前状态..."
"${DC[@]}" ps

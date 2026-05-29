#!/bin/bash
# 仅构建前端静态资源
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/frontend"

if [ ! -d "node_modules" ]; then
    echo "📦 安装前端依赖..."
    npm install --silent
fi

echo "📦 构建前端..."
npm run build

if [ $? -eq 0 ]; then
    echo "✅ 构建完成，输出到 backend/static/"
else
    echo "❌ 构建失败"
    exit 1
fi

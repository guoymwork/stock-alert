#!/bin/bash
# 股票预警系统 - 一键启动
ROOT="$(cd "$(dirname "$0")" && pwd)"

# ---- 1. Build frontend ----
echo "📦 构建前端..."
cd "$ROOT/frontend"
if [ ! -d "node_modules" ]; then
    echo "   安装前端依赖..."
    npm install --silent
fi
npm run build
if [ $? -ne 0 ]; then
    echo "❌ 前端构建失败"
    exit 1
fi
echo "✅ 前端构建完成"

# ---- 2. Check Python dependencies ----
cd "$ROOT/backend"
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "📦 安装后端依赖..."
    pip3 install -r requirements.txt -q
fi

# ---- 3. Kill existing process on port 8000 ----
lsof -ti :8000 | xargs kill 2>/dev/null

# ---- 4. Start ----
echo ""
echo "🚀 股票预警系统启动中..."
echo "📌 访问地址: http://localhost:8000"
echo ""

# Open browser after short delay
(sleep 2 && open http://localhost:8000 2>/dev/null) &

python3 run.py

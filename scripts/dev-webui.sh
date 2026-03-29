#!/bin/bash
# 同时启动后端和 WebUI（优化版本 - 减少不必要的热重载）

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🚀 启动 Flocks 开发环境...${NC}"

# 清理所有残留的 flocks 后端进程和端口
echo "🧹 清理现有进程..."
pkill -9 -f "uvicorn flocks.server.app" 2>/dev/null || true
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true
sleep 2

# 获取项目根目录
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

# 启动后端服务（只监控 flocks 源码目录）
echo -e "${GREEN}🔧 启动后端服务（端口 8000）...${NC}"
PYTHON="${PROJECT_ROOT}/.venv/bin/python"
nohup "${PYTHON}" -m uvicorn flocks.server.app:app \
    --host 127.0.0.1 \
    --port 8000 \
    --reload \
    --reload-dir flocks \
    --timeout-graceful-shutdown 3 \
    > /tmp/flocks-backend.log 2>&1 &

BACKEND_PID=$!
echo -e "${YELLOW}Backend PID: ${BACKEND_PID}${NC}"

# 等待后端启动（重试最多 30 秒）
echo "⏳ 等待后端启动..."
for i in $(seq 1 15); do
    if curl -s --max-time 2 http://localhost:8000/api/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 后端服务启动成功${NC}"
        echo -e "${YELLOW}📋 后端日志: tail -f /tmp/flocks-backend.log${NC}"
        break
    fi
    if [ $i -eq 15 ]; then
        echo -e "${RED}❌ 后端服务启动失败（超时 30 秒），查看日志:${NC}"
        tail -20 /tmp/flocks-backend.log
        exit 1
    fi
    sleep 2
done

# 启动前端服务
echo -e "${GREEN}🎨 启动 WebUI 前端（端口 5173）...${NC}"
cd webui

trap "echo '🛑 停止后端服务...'; kill $BACKEND_PID 2>/dev/null" EXIT

npm run dev

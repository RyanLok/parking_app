#!/usr/bin/env bash
# 生产环境启动脚本
# 用法：chmod +x start.sh && ./start.sh

set -e

cd "$(dirname "$0")"

export ENV=prod
export PORT=${PORT:-8000}

# 替换为你 Vercel 部署后的实际域名
export CORS_ORIGINS="${CORS_ORIGINS:-https://your-app.vercel.app,https://your-custom-domain.com}"

echo "🚀 启动 Parking API..."
echo "   端口: $PORT"
echo "   CORS: $CORS_ORIGINS"
echo "   数据目录: $(pwd)/data"

exec python3 -m uvicorn main:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --workers 1 \
  --log-level info

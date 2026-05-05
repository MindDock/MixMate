#!/usr/bin/env bash

echo "🛑 停止 MixMate..."

pkill -f "from mixmate.web.app import run_server" 2>/dev/null && echo "   ✅ Web 服务已停止" || echo "   ℹ️  Web 服务未运行"

echo ""
echo "💡 提示: Ollama 服务仍在后台运行"
echo "   如需停止: brew services stop ollama"

#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${1:-8088}"

echo ""
echo "🎬 MixMate - AI自动视频剪辑系统"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

PYTHON=""
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
elif [ -f "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
elif [ -f "/opt/miniconda3/bin/python" ]; then
    PYTHON="/opt/miniconda3/bin/python"
elif [ -f "$HOME/miniconda3/bin/python" ]; then
    PYTHON="$HOME/miniconda3/bin/python"
elif [ -f "$HOME/anaconda3/bin/python" ]; then
    PYTHON="$HOME/anaconda3/bin/python"
fi

if [ -z "$PYTHON" ]; then
    PYTHON="python3"
fi

echo "🐍 Python: $($PYTHON --version 2>&1)"

if ! $PYTHON -c "import flask" 2>/dev/null; then
    echo "📦 安装依赖..."
    $PYTHON -m pip install -r requirements.txt
fi

if ! command -v ffmpeg &>/dev/null; then
    echo "⚠️  未找到 ffmpeg，视频渲染功能将不可用"
    echo "   安装: brew install ffmpeg"
fi

if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
    echo "⚠️  Ollama 未运行，AI 视觉理解将回退到规则引擎"
    echo "   启动: ollama serve &"
    echo "   拉取视觉模型: ollama pull moondream:v2"
fi

mkdir -p mixmate/web/uploads mixmate/web/output

echo ""
echo "🚀 启动 Web UI → http://localhost:$PORT"
echo "   按 Ctrl+C 停止"
echo ""

$PYTHON -c "from mixmate.web.app import run_server; run_server(port=$PORT)"

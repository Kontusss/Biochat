#!/bin/bash
# ============================================
#  Biochat 一键启动脚本
#  引擎: Biochat  |  UI: Biochat Streamlit (ChatGPT 风格)
#  首次运行自动下载 ~11GB 数据湖，请耐心等待
# ============================================
#
# 安全提示：
#   API Key 请通过 .env 文件或环境变量配置，切勿硬编码在此脚本中。
#   详见 .env.example 了解所需环境变量。
#
# 用法：
#   bash start.sh              # Streamlit UI (推荐)
#   bash start.sh gradio       # Gradio UI (旧版)
# ============================================

set -e

UI_MODE="${1:-streamlit}"   # 默认 streamlit, 可选 gradio

# ── 激活 conda 环境 ──────────────────────────────────────────
if [ -f ~/miniconda3/etc/profile.d/conda.sh ]; then
    source ~/miniconda3/etc/profile.d/conda.sh
    conda activate biomni_e1
elif [ -f ~/anaconda3/etc/profile.d/conda.sh ]; then
    source ~/anaconda3/etc/profile.d/conda.sh
    conda activate biomni_e1
else
    echo "⚠️  Conda not found. Please activate biomni_e1 manually."
fi

# ── 切到项目目录 ──────────────────────────────────────────────
cd "$(dirname "$0")"

# ── 加载 .env 配置（如存在）───────────────────────────────────
if [ -f .env ]; then
    echo "📄 Loading environment from .env..."
    set -a
    source .env
    set +a
fi

# ── 显示当前配置 ──────────────────────────────────────────────
MODEL="${BIOCHAT_LLM:-${BIOMNI_LLM:-claude-sonnet-4-5}}"
SOURCE="${LLM_SOURCE:-auto}"
DATA="${BIOCHAT_DATA_PATH:-${BIOMNI_DATA_PATH:-./data}}"

echo "=========================================="
echo "  🧬 Biochat 启动中..."
echo "  引擎: Biochat"
echo "  模型: ${MODEL}"
echo "  Source: ${SOURCE}"
echo "  数据: ${DATA}"

if [ "$UI_MODE" = "gradio" ]; then
    echo "  UI: Gradio (旧版)"
    echo "  地址: http://localhost:7860"
    echo "=========================================="
    python -c "
from biomni.config import default_config
from biomni.agent import A1
agent = A1(path='${DATA}')
agent.launch_biochat_ui()
"
else
    echo "  UI: Streamlit (ChatGPT 风格)"
    echo "  地址: http://localhost:8501"
    echo "=========================================="
    streamlit run biomni/ui/biochat_streamlit.py
fi

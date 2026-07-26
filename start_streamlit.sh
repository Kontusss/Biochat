#!/bin/bash
# ============================================
#  Biochat Streamlit 一键启动脚本
#  引擎: Biomni
#  首次运行自动下载 ~11GB 数据湖，请耐心等待
# ============================================
#
# 安全提示：
#   API Key 请通过 .env 文件或环境变量配置，切勿硬编码在此脚本中。
#   详见 .env.example 了解所需环境变量。
#
# 用法：
#   bash start_streamlit.sh
# ============================================

set -e

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

# ── 显示当前配置（隐藏 API Key）───────────────────────────────
echo "=========================================="
echo "  🧬 Biochat Streamlit UI 启动中..."
echo "  引擎: Biomni"
echo "  模型: ${BIOCHAT_LLM:-${BIOMNI_LLM:-claude-sonnet-4-5}}"
echo "  Source: ${LLM_SOURCE:-auto}"
echo "  数据: ${BIOCHAT_DATA_PATH:-${BIOMNI_DATA_PATH:-./data}}"
echo "  前端: http://localhost:8501"
echo "=========================================="

# ── 启动 Streamlit ───────────────────────────────────────────
streamlit run biomni/ui/biochat_streamlit.py

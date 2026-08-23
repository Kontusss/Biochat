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
#   所有启动参数（UI 模式 / 绑定地址 / 端口）由
#   python -m biochat.ui.cli 解析；未知 UI 模式将以状态码 2 退出，
#   非回环绑定需要配置访问码或显式确认 (BIOCHAT_ALLOW_UNAUTHENTICATED_REMOTE)。
#
# 用法：
#   bash start.sh                    # Streamlit UI (推荐, 127.0.0.1)
#   bash start.sh gradio             # Gradio UI (旧版, 127.0.0.1)
#   BIOCHAT_HOST=127.0.0.1 bash start.sh streamlit
# ============================================

set -e

UI_MODE="${1:-streamlit}"   # streamlit (默认) | gradio

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

echo "=========================================="
echo "  🧬 Biochat 启动中..."
echo "  引擎: Biochat"
echo "  模型: ${BIOCHAT_LLM:-${BIOMNI_LLM:-claude-sonnet-4-5}}"
echo "  数据: ${BIOCHAT_DATA_PATH:-${BIOMNI_DATA_PATH:-./data}}"
echo "  UI: ${UI_MODE} (绑定 ${BIOCHAT_HOST:-127.0.0.1})"
echo "=========================================="

# ── 通过 CLI 模块启动（无 Python 源码插值，安全默认值）────────
exec python -m biochat.ui.cli --ui "$UI_MODE" --host "${BIOCHAT_HOST:-127.0.0.1}"

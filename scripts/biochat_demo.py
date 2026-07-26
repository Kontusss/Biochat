#!/usr/bin/env python3
"""
Biochat Demo Script — Quick start for Biochat.

This script demonstrates Biochat in action with a ProtChat-inspired UI.
Run it to launch the Biochat web interface with a pre-configured agent.

Usage:
    python scripts/biochat_demo.py

Requirements:
    - Biomni environment activated (conda activate biomni_e1)
    - API keys configured in .env file
    - Gradio 5.x installed (pip install 'gradio>=5.0,<6.0')

Biochat is built on Biomni (https://github.com/snap-stanford/Biomni).
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    """Launch the Biochat demo UI."""
    print("=" * 60)
    print("  🧬 Biochat Demo — Biomedical AI Agent")
    print("  Engine: Biomni")
    print("  UI: ProtChat-inspired Gradio")
    print("=" * 60)
    print()
    print("Starting Biochat...")
    print()

    # Import Biochat components
    try:
        from biomni.config import default_config
        from biomni.agent import A1
    except ImportError as e:
        print(f"❌ Failed to import Biomni core: {e}")
        print()
        print("Make sure you have:")
        print("  1. Activated the biomni_e1 environment")
        print("  2. Installed biomni package (pip install biomni --upgrade)")
        print()
        sys.exit(1)

    # ── Configuration ──────────────────────────────────────
    # You can customize these settings before launching

    # LLM Configuration
    # default_config.llm = "claude-sonnet-4-20250514"  # Default
    # default_config.llm = "gpt-4"                      # OpenAI
    # default_config.llm = "deepseek-chat"              # DeepSeek
    # default_config.source = "Custom"                  # For custom providers
    # default_config.base_url = "https://api.deepseek.com/v1"
    # default_config.api_key = "your-api-key"

    # Performance settings
    default_config.timeout_seconds = 600  # Increase for complex tasks

    # Data licensing
    # default_config.commercial_mode = True  # Exclude non-commercial datasets

    # ── Initialize Agent ────────────────────────────────────
    print("📦 Initializing Biochat agent...")
    print("   (First run may download ~11GB data lake — please be patient)")
    print()

    try:
        agent = A1(path="./data")
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        print()
        print("Common issues:")
        print("  - Missing API keys: check your .env file")
        print("  - Network issues: data lake download may have failed")
        print("  - Missing dependencies: check package installation")
        sys.exit(1)

    # ── Launch UI ───────────────────────────────────────────
    print()
    print("🎨 Launching Biochat ProtChat-inspired UI...")
    print("   Open http://localhost:7860 in your browser")
    print()

    try:
        # Option 1: Use the new Biochat UI (recommended)
        agent.launch_biochat_ui()

        # Option 2: Use the original Biomni Gradio interface
        # agent.launch_gradio_demo()
    except KeyboardInterrupt:
        print()
        print("👋 Biochat demo stopped.")
    except Exception as e:
        print(f"❌ UI launch failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

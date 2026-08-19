#!/usr/bin/env python3
"""Biochat Streamlit Demo Launcher.

Launches the ProtChat-inspired Streamlit UI for Biochat.
Requires the Biochat environment and Streamlit.

Usage
-----
    python scripts/biochat_streamlit_demo.py

    Or directly:

    streamlit run biochat/ui/biochat_streamlit.py

The UI will be available at http://localhost:8501
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    app = root / "biochat" / "ui" / "biochat_streamlit.py"

    if not app.exists():
        print(f"❌ Streamlit app not found: {app}")
        sys.exit(1)

    print("=" * 60)
    print("  🧬 Biochat Streamlit Demo")
    print("  Engine: Biochat")
    print("  UI: ProtChat-inspired Streamlit")
    print("=" * 60)
    print()
    print("  Open http://localhost:8501 after launch")
    print()

    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(app)],
        cwd=str(root),
        check=False,
    )


if __name__ == "__main__":
    main()

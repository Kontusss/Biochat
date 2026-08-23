"""Command-line launcher for the Biochat UIs.

Usage::

    python -m biochat.ui.cli                       # Streamlit (default)
    python -m biochat.ui.cli --ui gradio --host 127.0.0.1

Configuration is read through ``BiochatSettings``; unknown UI modes exit
with status 2, and unsafe non-loopback binds are rejected by
:func:`biochat.ui.auth.validate_remote_exposure`.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_UI_CHOICES = ("streamlit", "gradio")
_DEFAULT_HOST = "127.0.0.1"
_STREAMLIT_APP = Path(__file__).with_name("biochat_streamlit.py")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m biochat.ui.cli",
        description="Launch a Biochat UI with safe defaults.",
    )
    parser.add_argument(
        "--ui",
        choices=_UI_CHOICES,
        default="streamlit",
        help="UI flavor to launch (default: %(default)s).",
    )
    parser.add_argument(
        "--host",
        default=_DEFAULT_HOST,
        help="Server bind address (default: %(default)s).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Optional server port override.",
    )
    parser.add_argument(
        "--share",
        action="store_true",
        help="Create a public Gradio share link (gradio UI only).",
    )
    return parser


def _run_streamlit(host: str, port: int | None) -> int:
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(_STREAMLIT_APP),
        "--server.address",
        host,
    ]
    if port is not None:
        cmd += ["--server.port", str(port)]
    completed = subprocess.run(cmd)
    return completed.returncode


def _run_gradio(host: str, share: bool) -> int:
    from biochat.agent import A1
    from biochat.core.settings import biochat_settings

    agent = A1(path=biochat_settings.data_path)
    agent.launch_biochat_ui(server_name=host, share=share)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    from biochat.core.settings import biochat_settings
    from biochat.ui.auth import validate_remote_exposure

    try:
        validate_remote_exposure(args.host, biochat_settings)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.ui == "gradio":
        return _run_gradio(args.host, args.share)
    return _run_streamlit(args.host, args.port)


if __name__ == "__main__":
    sys.exit(main())

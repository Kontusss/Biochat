"""
UI launcher — extracted from ``A1.launch_biochat_ui()``.

Delegates to the Biochat UI module.  The legacy ``launch_gradio_demo()``
is kept in the original ``a1.py`` for backward compatibility.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from biochat.agent.a1 import A1


def launch_biochat_ui_from_agent(
    agent: "A1",
    thread_id: int = 42,
    share: bool = False,
    server_name: str = "127.0.0.1",
    require_verification: bool = False,
) -> None:
    """Launch the ProtChat-inspired Biochat UI for an A1 agent.

    This is a standalone function (not a method) that takes an *agent*
    instance as its first argument — making it testable without
    instantiating ``A1``.

    Args:
        agent: An initialised ``A1`` instance.
        thread_id: Thread ID for conversation state.
        share: Whether to create a public shareable link.
        server_name: Server host to bind to.
        require_verification: Require access-code verification.
    """
    from biochat.core.settings import biochat_settings as _settings
    from biochat.ui.auth import validate_remote_exposure

    # Reject unsafe non-loopback binds before any UI is built.
    validate_remote_exposure(server_name, _settings)

    from biochat.ui.biochat_ui import launch_biochat_ui as _launch

    _launch(
        agent=agent,
        thread_id=thread_id,
        share=share,
        server_name=server_name,
        require_verification=require_verification,
    )

"""
Biochat UI Module

Provides a ProtChat-inspired Gradio interface for the Biochat agent,
built on the Biochat engine. This module adds modern styling, a chat-centered
layout, tool sidebar, and status indicators while preserving all core
scientific functionality.
"""

from .biochat_theme import BiochatTheme, get_biochat_theme
from .biochat_ui import create_biochat_ui, launch_biochat_ui
from .biochat_about import launch_biochat_about

__all__ = [
    "BiochatTheme",
    "get_biochat_theme",
    "create_biochat_ui",
    "launch_biochat_ui",
    "launch_biochat_about",
]

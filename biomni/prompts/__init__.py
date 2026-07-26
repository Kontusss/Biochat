"""
Biochat System Prompt Module.

Extracted from ``biomni.agent.a1._generate_system_prompt()`` into a
maintainable, testable module.  The ``SystemPromptBuilder`` class
assembles the agent's system prompt from configuration, tool
descriptions, data lake content, and know-how documents.
"""

from biomni.prompts.system_prompt import SystemPromptBuilder

__all__ = ["SystemPromptBuilder"]

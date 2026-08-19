"""
Biochat Configuration Management (backward-compatible)

Simple configuration class for centralizing common settings.
Maintains full backward compatibility with existing code.
"""

import os
from dataclasses import dataclass

# Load .env file early so config values are available even when
# biochat.agent (which also calls load_dotenv) hasn't been imported yet.
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(".env", override=False)
except Exception:
    pass


@dataclass
class BiochatConfig:
    """Central configuration for Biochat agent (backward-compatible).

    All settings are optional and have sensible defaults.
    API keys are still read from environment variables to maintain
    compatibility with existing .env file structure.

    Usage:
        # Create config with defaults
        config = BiochatConfig()

        # Override specific settings
        config = BiochatConfig(llm="gpt-4", timeout_seconds=1200)

        # Modify after creation
        config.path = "./custom_data"
    """

    # Data and execution settings
    path: str = "./data"
    timeout_seconds: int = 600

    # LLM settings (API keys still from environment)
    llm: str = "claude-sonnet-4-5"
    temperature: float = 0.7

    # Tool settings
    use_tool_retriever: bool = True
    # Runtime tool profile: "minimal" (demo + antibody pipeline + engine
    # glue) or "full" (every attributed Biochat tool).
    tool_profile: str = "full"

    # Data licensing settings
    commercial_mode: bool = False  # If True, excludes non-commercial datasets

    # Custom model settings (for custom LLM serving)
    base_url: str | None = None
    api_key: str | None = None  # Only for custom models, not provider API keys

    # LLM source (auto-detected if None)
    source: str | None = None

    # Third-party integrations
    protocols_io_access_token: str | None = None

    def __post_init__(self):
        """Load any environment variable overrides if they exist."""
        # Check for environment variable overrides (optional)
        # Support both BIOMNI_* and BIOCHAT_* env vars for compatibility
        if os.getenv("BIOCHAT_PATH") or os.getenv("BIOMNI_PATH") or os.getenv("BIOMNI_DATA_PATH") or os.getenv("BIOCHAT_DATA_PATH"):
            self.path = os.getenv("BIOCHAT_PATH") or os.getenv("BIOMNI_PATH") or os.getenv("BIOMNI_DATA_PATH") or os.getenv("BIOCHAT_DATA_PATH")
        if os.getenv("BIOCHAT_TIMEOUT_SECONDS") or os.getenv("BIOMNI_TIMEOUT_SECONDS"):
            self.timeout_seconds = int(os.getenv("BIOCHAT_TIMEOUT_SECONDS") or os.getenv("BIOMNI_TIMEOUT_SECONDS"))
        if os.getenv("BIOCHAT_LLM") or os.getenv("BIOMNI_LLM") or os.getenv("BIOCHAT_LLM_MODEL") or os.getenv("BIOMNI_LLM_MODEL"):
            self.llm = os.getenv("BIOCHAT_LLM") or os.getenv("BIOMNI_LLM") or os.getenv("BIOCHAT_LLM_MODEL") or os.getenv("BIOMNI_LLM_MODEL")
        if os.getenv("BIOCHAT_USE_TOOL_RETRIEVER") or os.getenv("BIOMNI_USE_TOOL_RETRIEVER"):
            val = os.getenv("BIOCHAT_USE_TOOL_RETRIEVER") or os.getenv("BIOMNI_USE_TOOL_RETRIEVER")
            self.use_tool_retriever = val.lower() == "true"
        if os.getenv("BIOCHAT_TOOL_PROFILE") or os.getenv("BIOMNI_TOOL_PROFILE"):
            profile = (os.getenv("BIOCHAT_TOOL_PROFILE") or os.getenv("BIOMNI_TOOL_PROFILE")).lower()
            if profile in ("minimal", "full"):
                self.tool_profile = profile
        if os.getenv("BIOCHAT_COMMERCIAL_MODE") or os.getenv("BIOMNI_COMMERCIAL_MODE"):
            val = os.getenv("BIOCHAT_COMMERCIAL_MODE") or os.getenv("BIOMNI_COMMERCIAL_MODE")
            self.commercial_mode = val.lower() == "true"
        if os.getenv("BIOCHAT_TEMPERATURE") or os.getenv("BIOMNI_TEMPERATURE"):
            self.temperature = float(os.getenv("BIOCHAT_TEMPERATURE") or os.getenv("BIOMNI_TEMPERATURE"))
        if os.getenv("BIOCHAT_CUSTOM_BASE_URL") or os.getenv("BIOMNI_CUSTOM_BASE_URL") or os.getenv("CUSTOM_MODEL_BASE_URL"):
            self.base_url = os.getenv("BIOCHAT_CUSTOM_BASE_URL") or os.getenv("BIOMNI_CUSTOM_BASE_URL") or os.getenv("CUSTOM_MODEL_BASE_URL")
        if os.getenv("BIOCHAT_CUSTOM_API_KEY") or os.getenv("BIOMNI_CUSTOM_API_KEY") or os.getenv("CUSTOM_MODEL_API_KEY"):
            self.api_key = os.getenv("BIOCHAT_CUSTOM_API_KEY") or os.getenv("BIOMNI_CUSTOM_API_KEY") or os.getenv("CUSTOM_MODEL_API_KEY")
        if os.getenv("BIOCHAT_SOURCE") or os.getenv("BIOMNI_SOURCE") or os.getenv("LLM_SOURCE"):
            self.source = os.getenv("BIOCHAT_SOURCE") or os.getenv("BIOMNI_SOURCE") or os.getenv("LLM_SOURCE")

        # Protocols.io access token (prefer specific env vars)
        env_token = os.getenv("PROTOCOLS_IO_ACCESS_TOKEN") or os.getenv("BIOCHAT_PROTOCOLS_IO_ACCESS_TOKEN") or os.getenv("BIOMNI_PROTOCOLS_IO_ACCESS_TOKEN")
        if env_token:
            self.protocols_io_access_token = env_token

    def to_dict(self) -> dict:
        """Convert config to dictionary for easy access."""
        return {
            "path": self.path,
            "timeout_seconds": self.timeout_seconds,
            "llm": self.llm,
            "temperature": self.temperature,
            "use_tool_retriever": self.use_tool_retriever,
            "tool_profile": self.tool_profile,
            "commercial_mode": self.commercial_mode,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "source": self.source,
        }


# Global default config instance (optional, for convenience)
default_config = BiochatConfig()


# ═══════════════════════════════════════════════════════════════════
# Bridge: sync legacy default_config → new BiochatSettings
# ═══════════════════════════════════════════════════════════════════
#
# When the user writes ``default_config.llm = "gpt-4"``, we forward
# the write to the new ``biochat_settings`` singleton so the service
# layer stays in sync.  This preserves backward compatibility while
# encouraging migration to ``biochat_settings``.
#

def _sync_legacy_to_new() -> None:
    """Copy legacy default_config values into the new biochat_settings."""
    try:
        from biochat.core.settings import biochat_settings as _new

        _new.llm_model = default_config.llm
        _new.llm_source = default_config.source
        _new.data_path = default_config.path
        _new.timeout_seconds = default_config.timeout_seconds
        _new.use_tool_retriever = default_config.use_tool_retriever
        _new.commercial_mode = default_config.commercial_mode
        _new.base_url = default_config.base_url
        _new.api_key = default_config.api_key
    except Exception:
        pass  # Best-effort; new settings module may not be available

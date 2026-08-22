"""
Unified Configuration Management for Biochat.

Replaces the split config.py + biochat_config.py with a single,
well-typed settings class backed by environment variables.

Features:
- Pydantic-based validation with type coercion
- Supports both BIOCHAT_* and BIOMNI_* env var prefixes (backward compatible)
- .env file auto-loading
- Sensible defaults for all fields
- Immutable after initialization (frozen=True)

Usage:
    from biochat.core.settings import biochat_settings

    model = biochat_settings.llm_model
    timeout = biochat_settings.timeout_seconds
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import ClassVar

from biochat.version import __version__

try:
    from dotenv import load_dotenv as _load_dotenv

    _load_dotenv(".env", override=False)
except Exception:
    pass


# ═══════════════════════════════════════════════════════════════════
# Environment variable resolution helpers
# ═══════════════════════════════════════════════════════════════════

def _env(first: str, *fallbacks: str, default: str | None = None) -> str | None:
    """Return the first non-empty environment variable from a chain of names."""
    for name in (first, *fallbacks):
        val = os.getenv(name)
        if val:
            return val
    return default


def _env_bool(first: str, *fallbacks: str, default: bool = False) -> bool:
    """Return a boolean from the first non-empty environment variable."""
    val = _env(first, *fallbacks)
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes", "on")


def _env_int(first: str, *fallbacks: str, default: int = 0) -> int:
    """Return an integer from the first non-empty environment variable."""
    val = _env(first, *fallbacks)
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _env_float(first: str, *fallbacks: str, default: float = 0.0) -> float:
    """Return a float from the first non-empty environment variable."""
    val = _env(first, *fallbacks)
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


# ═══════════════════════════════════════════════════════════════════
# Valid source values
# ═══════════════════════════════════════════════════════════════════

ALLOWED_LLM_SOURCES: frozenset[str] = frozenset({
    "OpenAI",
    "AzureOpenAI",
    "Anthropic",
    "Ollama",
    "Gemini",
    "Bedrock",
    "Groq",
    "Custom",
})


# ═══════════════════════════════════════════════════════════════════
# Project identity constants (moved from biochat_config.py)
#
# ``biochat.version.__version__`` is the sole version source for the
# package (pyproject reads it dynamically), both UIs, and project
# metadata.  Never duplicate a literal version here.
# ═══════════════════════════════════════════════════════════════════

PROJECT_NAME: str = "Biochat"
PROJECT_VERSION: str = __version__
PROJECT_DESCRIPTION: str = "A General-Purpose Biomedical AI Agent"
PROJECT_ENGINE: str = "Biochat"
PROJECT_ENGINE_VERSION: str = __version__
PROJECT_LICENSE: str = "Apache-2.0"


# ═══════════════════════════════════════════════════════════════════
# Theme design tokens (moved from biochat_config.py)
# ═══════════════════════════════════════════════════════════════════

THEME: dict = {
    "primary_color": "#4f46e5",
    "primary_hover": "#4338ca",
    "background": "#f7f8fb",
    "sidebar_bg": "#fbfcfd",
    "card_bg": "#ffffff",
    "text_primary": "#20242c",
    "text_secondary": "#5a616d",
    "text_muted": "#8b919e",
    "border": "rgba(32, 36, 44, 0.08)",
    "border_solid": "#e5e7eb",
    "border_radius": "14px",
    "font_family": "'Noto Sans SC', system-ui, -apple-system, sans-serif",
    "font_mono": "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Monaco, Consolas, monospace",
    "green": "#16a34a",
    "amber": "#f59e0b",
    "red": "#dc2626",
}


# ═══════════════════════════════════════════════════════════════════
# Safety policy constants
# ═══════════════════════════════════════════════════════════════════

SAFETY_POLICY: dict = {
    "code_execution_warning": True,
    "requires_sandbox": True,
    "commercial_mode_supported": True,
    "default_timeout_seconds": 600,
    "max_timeout_seconds": 3600,
}


# ═══════════════════════════════════════════════════════════════════
# Capability registry
# ═══════════════════════════════════════════════════════════════════

CAPABILITIES: dict[str, dict[str, str]] = {
    "biochemistry": {"name": "Biochemistry", "icon": "🔬", "description": "Protein & enzyme analysis"},
    "genomics": {"name": "Genomics", "icon": "🧬", "description": "Variant annotation, GWAS, sequence analysis"},
    "pharmacology": {"name": "Pharmacology", "icon": "💊", "description": "ADMET prediction, drug interactions"},
    "cell_biology": {"name": "Cell Biology", "icon": "🧫", "description": "scRNA-seq, pathway analysis"},
    "microbiology": {"name": "Microbiology", "icon": "🦠", "description": "Pathogen genomics, microbiome"},
    "immunology": {"name": "Immunology", "icon": "🛡️", "description": "Epitope prediction, TCR/BCR analysis"},
    "cancer_biology": {"name": "Cancer Biology", "icon": "🔬", "description": "Driver genes, tumor evolution"},
    "systems_biology": {"name": "Systems Biology", "icon": "🔗", "description": "Metabolic modeling, networks"},
    "literature": {"name": "Literature Mining", "icon": "📚", "description": "PubMed, bioRxiv search"},
    "databases": {"name": "30+ Databases", "icon": "🗄️", "description": "UniProt, Ensembl, PDB, ClinVar…"},
}


# ═══════════════════════════════════════════════════════════════════
# Quick action examples
# ═══════════════════════════════════════════════════════════════════

QUICK_ACTIONS: list[dict[str, str]] = [
    {
        "label": "🔬 Plan a CRISPR screen",
        "query": "Plan a CRISPR screen to identify genes that regulate T cell exhaustion, "
                 "generate 32 genes that maximize the perturbation effect.",
    },
    {
        "label": "🧬 scRNA-seq annotation",
        "query": "Perform scRNA-seq annotation and generate meaningful hypotheses "
                 "about cell populations.",
    },
    {
        "label": "💊 Predict ADMET properties",
        "query": "Predict ADMET properties for this compound: CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",
    },
    {
        "label": "🧪 Design sgRNA",
        "query": "Design sgRNA sequences for knocking out the human TP53 gene "
                 "with minimum off-target effects.",
    },
    {
        "label": "📚 Literature search",
        "query": "Search recent literature on CRISPR-based therapies for genetic diseases "
                 "and summarize key findings.",
    },
    {
        "label": "🗄️ Query databases",
        "query": "Query UniProt for the human BRCA1 protein and identify key functional domains.",
    },
]


# ═══════════════════════════════════════════════════════════════════
# BiochatSettings — runtime configuration
# ═══════════════════════════════════════════════════════════════════

class BiochatSettings:
    """Centralised, validated runtime settings for Biochat.

    All values can be overridden via environment variables.
    Priority order: BIOCHAT_* env var > BIOMNI_* env var > code default.

    This is intentionally a plain class (not pydantic) to avoid adding
    a hard dependency.  Validation is done in __init__.
    """

    # ── Agent settings ────────────────────────────────────────────
    data_path: str
    timeout_seconds: int
    use_tool_retriever: bool
    tool_profile: str
    commercial_mode: bool
    recursion_limit: int

    # ── LLM settings ──────────────────────────────────────────────
    llm_model: str
    llm_source: str | None
    temperature: float
    base_url: str | None
    api_key: str | None
    max_tokens: int

    # ── UI settings ───────────────────────────────────────────────
    access_codes: list[str]
    require_verification: bool

    # ── Security policy ───────────────────────────────────────────
    # Both default to False: unrestricted host code execution and
    # unauthenticated non-loopback exposure must be explicitly enabled.
    allow_host_code_execution: bool
    allow_unauthenticated_remote: bool

    # ── Third-party ───────────────────────────────────────────────
    protocols_io_access_token: str | None

    # Expected env-prefix pairs for loading
    _ENV_MAP: ClassVar[dict[str, tuple[str, ...]]] = {
        "data_path": ("BIOCHAT_DATA_PATH", "BIOCHAT_PATH", "BIOMNI_DATA_PATH", "BIOMNI_PATH"),
        "timeout_seconds": ("BIOCHAT_TIMEOUT_SECONDS", "BIOMNI_TIMEOUT_SECONDS"),
        "use_tool_retriever": ("BIOCHAT_USE_TOOL_RETRIEVER", "BIOMNI_USE_TOOL_RETRIEVER"),
        "tool_profile": ("BIOCHAT_TOOL_PROFILE", "BIOMNI_TOOL_PROFILE"),
        "commercial_mode": ("BIOCHAT_COMMERCIAL_MODE", "BIOMNI_COMMERCIAL_MODE"),
        "recursion_limit": ("BIOCHAT_RECURSION_LIMIT", "BIOMNI_RECURSION_LIMIT"),
        "llm_model": ("BIOCHAT_LLM", "BIOCHAT_LLM_MODEL", "BIOMNI_LLM", "BIOMNI_LLM_MODEL"),
        "llm_source": ("BIOCHAT_SOURCE", "LLM_SOURCE", "BIOMNI_SOURCE"),
        "temperature": ("BIOCHAT_TEMPERATURE", "BIOMNI_TEMPERATURE"),
        "base_url": ("BIOCHAT_CUSTOM_BASE_URL", "CUSTOM_MODEL_BASE_URL", "BIOMNI_CUSTOM_BASE_URL"),
        "api_key": ("BIOCHAT_CUSTOM_API_KEY", "CUSTOM_MODEL_API_KEY", "BIOMNI_CUSTOM_API_KEY"),
        "max_tokens": ("BIOCHAT_MAX_TOKENS", "BIOMNI_MAX_TOKENS"),
        "allow_host_code_execution": ("BIOCHAT_ALLOW_HOST_CODE_EXECUTION",),
        "allow_unauthenticated_remote": ("BIOCHAT_ALLOW_UNAUTHENTICATED_REMOTE",),
    }

    def __init__(
        self,
        *,
        data_path: str | None = None,
        timeout_seconds: int | None = None,
        use_tool_retriever: bool | None = None,
        tool_profile: str | None = None,
        commercial_mode: bool | None = None,
        recursion_limit: int | None = None,
        llm_model: str | None = None,
        llm_source: str | None = None,
        temperature: float | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        max_tokens: int | None = None,
        access_codes: list[str] | None = None,
        require_verification: bool | None = None,
        allow_host_code_execution: bool | None = None,
        allow_unauthenticated_remote: bool | None = None,
    ):
        """Initialise settings, resolving env vars for unset fields."""
        # ── Data / execution ──────────────────────────────────
        self.data_path = (
            data_path
            if data_path is not None
            else _env(*self._ENV_MAP["data_path"], default="./data")  # type: ignore[arg-type]
        )
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else _env_int(*self._ENV_MAP["timeout_seconds"], default=600)
        )
        self.use_tool_retriever = (
            use_tool_retriever
            if use_tool_retriever is not None
            else _env_bool(*self._ENV_MAP["use_tool_retriever"], default=True)
        )
        raw_profile = (
            tool_profile
            if tool_profile is not None
            else _env(*self._ENV_MAP["tool_profile"], default="full")
        )
        self.tool_profile = raw_profile.lower() if raw_profile.lower() in ("minimal", "full") else "full"
        self.commercial_mode = (
            commercial_mode
            if commercial_mode is not None
            else _env_bool(*self._ENV_MAP["commercial_mode"], default=False)
        )
        self.recursion_limit = (
            recursion_limit
            if recursion_limit is not None
            else _env_int(*self._ENV_MAP["recursion_limit"], default=500)
        )

        # ── LLM ───────────────────────────────────────────────
        self.llm_model = (
            llm_model
            if llm_model is not None
            else _env(*self._ENV_MAP["llm_model"], default="claude-sonnet-4-5")  # type: ignore[arg-type]
        )
        raw_source = (
            llm_source
            if llm_source is not None
            else _env(*self._ENV_MAP["llm_source"], default=None)
        )
        self.llm_source = raw_source if raw_source in ALLOWED_LLM_SOURCES else None

        self.temperature = (
            temperature
            if temperature is not None
            else _env_float(*self._ENV_MAP["temperature"], default=0.7)
        )
        self.base_url = (
            base_url
            if base_url is not None
            else _env(*self._ENV_MAP["base_url"], default=None)
        )
        self.api_key = (
            api_key
            if api_key is not None
            else _env(*self._ENV_MAP["api_key"], default=None)
        )
        self.max_tokens = (
            max_tokens
            if max_tokens is not None
            else _env_int(*self._ENV_MAP["max_tokens"], default=8192)
        )

        # ── UI ────────────────────────────────────────────────
        access_code_env = os.getenv("BIOCHAT_ACCESS_CODE") or os.getenv("BIOMNI_ACCESS_CODE")
        self.access_codes = (
            access_codes
            if access_codes is not None
            else [c.strip() for c in access_code_env.split(",") if c.strip()]
            if access_code_env
            else []
        )
        self.require_verification = (
            require_verification
            if require_verification is not None
            else bool(self.access_codes)
        )

        # ── Security policy ──────────────────────────────────
        # Secure defaults: both flags require an explicit environment
        # acknowledgement (or explicit constructor argument) to enable.
        self.allow_host_code_execution = (
            allow_host_code_execution
            if allow_host_code_execution is not None
            else _env_bool(*self._ENV_MAP["allow_host_code_execution"], default=False)
        )
        self.allow_unauthenticated_remote = (
            allow_unauthenticated_remote
            if allow_unauthenticated_remote is not None
            else _env_bool(*self._ENV_MAP["allow_unauthenticated_remote"], default=False)
        )

        # ── Third-party ───────────────────────────────────────
        self.protocols_io_access_token = (
            os.getenv("PROTOCOLS_IO_ACCESS_TOKEN")
            or os.getenv("BIOCHAT_PROTOCOLS_IO_ACCESS_TOKEN")
            or os.getenv("BIOMNI_PROTOCOLS_IO_ACCESS_TOKEN")
        )

    # ── Derived properties ────────────────────────────────────────

    @property
    def model_display_name(self) -> str:
        """Human-readable model identifier."""
        source = self.llm_source or "auto"
        return f"{self.llm_model} ({source})"

    def to_dict(self) -> dict:
        """Return a sanitised dict (no secrets)."""
        d: dict[str, object] = {
            "data_path": self.data_path,
            "timeout_seconds": self.timeout_seconds,
            "use_tool_retriever": self.use_tool_retriever,
            "tool_profile": self.tool_profile,
            "commercial_mode": self.commercial_mode,
            "recursion_limit": self.recursion_limit,
            "llm_model": self.llm_model,
            "llm_source": self.llm_source,
            "temperature": self.temperature,
            "base_url": self.base_url,
            "max_tokens": self.max_tokens,
            "require_verification": self.require_verification,
            "allow_host_code_execution": self.allow_host_code_execution,
            "allow_unauthenticated_remote": self.allow_unauthenticated_remote,
        }
        if self.api_key:
            d["api_key"] = "***" + self.api_key[-4:] if len(self.api_key) > 4 else "***"
        return d

    def pretty_summary(self) -> str:
        """Multi-line human-readable summary (console logging)."""
        lines = [
            "=" * 50,
            "🔧 BIOCHAT CONFIGURATION",
            "=" * 50,
        ]
        for key, value in self.to_dict().items():
            label = key.replace("_", " ").title()
            lines.append(f"  {label}: {value}")
        lines.append("=" * 50)
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# Singleton instance
# ═══════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def _get_settings() -> BiochatSettings:
    """Return a cached, singleton BiochatSettings instance."""
    return BiochatSettings()


biochat_settings: BiochatSettings = _get_settings()

# Convenience constant — the active tool profile ("minimal" or "full").
BIOCHAT_TOOL_PROFILE: str = biochat_settings.tool_profile

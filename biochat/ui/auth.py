"""UI authentication and remote-exposure boundary.

Access codes come exclusively from ``BiochatSettings`` (environment
configuration) — never literals — and comparisons use
``hmac.compare_digest``.  Non-loopback binds without configured
authentication are rejected unless the operator explicitly acknowledged
the risk via ``BIOCHAT_ALLOW_UNAUTHENTICATED_REMOTE=true``.
"""

from __future__ import annotations

import hmac

from biochat.core.errors import ConfigError

# Hosts considered loopback for exposure purposes.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def verify_access_code(candidate: object, configured_codes: list[str] | None) -> bool:
    """Return True when *candidate* matches one of the configured codes.

    Comparison is constant-time per configured code.  Non-string
    candidates never raise.
    """
    if not isinstance(candidate, str):
        return False
    candidate_bytes = candidate.encode("utf-8")
    for code in configured_codes or []:
        if not isinstance(code, str):
            continue
        if hmac.compare_digest(candidate_bytes, code.encode("utf-8")):
            return True
    return False


def is_loopback_host(host: str | None) -> bool:
    """True when *host* binds only the local machine."""
    return (host or "").strip().lower() in _LOOPBACK_HOSTS


def validate_remote_exposure(host: str | None, settings) -> None:
    """Reject unsafe non-loopback exposure.

    A non-loopback bind requires either configured access codes or an
    explicit ``allow_unauthenticated_remote`` acknowledgement in
    *settings*; otherwise :class:`ConfigError` is raised.
    """
    if is_loopback_host(host):
        return None
    if getattr(settings, "access_codes", None):
        return None
    if getattr(settings, "allow_unauthenticated_remote", False):
        return None
    raise ConfigError(
        "Refusing to bind Biochat to a non-loopback address without "
        "authentication. Configure access codes (BIOCHAT_ACCESS_CODE) or "
        "explicitly acknowledge unauthenticated remote exposure by setting "
        "BIOCHAT_ALLOW_UNAUTHENTICATED_REMOTE=true."
    )

"""Environment descriptor catalog — replaces the upstream env_desc modules.

Data lives in ``catalog.yaml``; the ``biochat.env_desc`` /
``biochat.env_desc_cm`` modules are thin compatibility adapters.
"""

from biochat.environment.registry import EnvironmentCatalog, get_environment_catalog

__all__ = ["EnvironmentCatalog", "get_environment_catalog"]

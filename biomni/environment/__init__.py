"""Environment descriptor catalog — replaces the upstream env_desc modules.

Data lives in ``catalog.yaml``; the ``biomni.env_desc`` /
``biomni.env_desc_cm`` modules are thin compatibility adapters.
"""

from biomni.environment.registry import EnvironmentCatalog, get_environment_catalog

__all__ = ["EnvironmentCatalog", "get_environment_catalog"]

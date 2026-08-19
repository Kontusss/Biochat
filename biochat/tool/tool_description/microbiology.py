"""Adapter — microbiology tool descriptions now live in catalog.yaml.

The original Python literals were migrated to
``biochat/tool/tool_description/catalog.yaml`` by
``scripts/build_tool_catalog.py``; the upstream data is preserved there
verbatim (Apache-2.0, snap-stanford/Biomni).
"""

from biochat.tool.tool_description._catalog_loader import load_tool_description

description = load_tool_description("microbiology")

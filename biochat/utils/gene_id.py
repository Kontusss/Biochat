"""Gene ID resolution utilities.

Replaces the original ``ID`` enum, ``get_gene_id``, and three
``_get_gene_id_*`` functions from ``utils.py`` (lines 589-652).

Uses a dictionary dispatch pattern instead of if/elif.
"""

from __future__ import annotations

import enum

import requests

# ═══════════════════════════════════════════════════════════════
# Gene identifier type enum
# ═══════════════════════════════════════════════════════════════

class GeneIDType(enum.Enum):
    """Supported gene identifier formats."""
    ENTREZ = "Entrez"
    ENSEMBL = "Ensembl without version"
    ENSEMBL_W_VERSION = "Ensembl with version"


# ═══════════════════════════════════════════════════════════════
# Resolvers
# ═══════════════════════════════════════════════════════════════

def resolve_entrez_id(gene_symbol: str) -> int | None:
    """Look up Entrez gene ID via mygene.info."""
    resp = requests.get(
        "https://mygene.info/v3/query",
        params={"species": "human", "q": f"symbol:{gene_symbol}"},
        timeout=10,
    )
    data = resp.json()
    hits = data.get("hits", [])
    return hits[0].get("entrezgene") if hits else None


def resolve_ensembl_id(gene_symbol: str) -> str | None:
    """Look up Ensembl gene ID (no version) via mygene.info."""
    resp = requests.get(
        "https://mygene.info/v3/query",
        params={"species": "human", "fields": "ensembl", "q": f"symbol:{gene_symbol}"},
        timeout=10,
    )
    data = resp.json()
    hits = data.get("hits", [])
    if not hits:
        return None
    ensembl = hits[0].get("ensembl")
    if isinstance(ensembl, list):
        return ensembl[0].get("gene") if ensembl else None
    return ensembl.get("gene") if isinstance(ensembl, dict) else None


def resolve_ensembl_versioned_id(gene_symbol: str) -> str | None:
    """Look up Ensembl gene ID (with version) via GTEx Portal."""
    resp = requests.get(
        "https://gtexportal.org/api/v2/reference/gene",
        params={"geneId": gene_symbol},
        timeout=10,
    )
    data = resp.json()
    hits = data.get("data", [])
    return hits[0].get("gencodeId") if hits else None


# ═══════════════════════════════════════════════════════════════
# Dispatcher
# ═══════════════════════════════════════════════════════════════

_RESOLVERS: dict[GeneIDType, object] = {
    GeneIDType.ENTREZ:            resolve_entrez_id,
    GeneIDType.ENSEMBL:           resolve_ensembl_id,
    GeneIDType.ENSEMBL_W_VERSION: resolve_ensembl_versioned_id,
}


def get_gene_id(gene_symbol: str, id_type: GeneIDType) -> int | str | None:
    """Resolve *gene_symbol* to the requested identifier type.

    Args:
        gene_symbol: HGNC gene symbol (e.g. ``"CDK2"``).
        id_type: Desired identifier format.

    Returns:
        The identifier if found, or ``None``.
    """
    resolver = _RESOLVERS.get(id_type)
    if resolver is None:
        raise ValueError(f"Unsupported gene ID type: {id_type}")
    return resolver(gene_symbol)  # type: ignore[operator]


# ── Backward-compatible aliases ─────────────────────────────────
ID = GeneIDType
_get_gene_id_entrez = resolve_entrez_id
_get_gene_id_ensembl = resolve_ensembl_id
_get_gene_id_ensembl_with_version = resolve_ensembl_versioned_id

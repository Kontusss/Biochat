"""
Biochat Project Configuration

Biochat-specific configuration constants and metadata.
This module does NOT modify Biomni core configuration — it adds
Biochat's project-level settings on top.
"""

# ── Project Identity ───────────────────────────────────────
PROJECT_NAME = "Biochat"
PROJECT_VERSION = "2.0.0"
PROJECT_DESCRIPTION = "A General-Purpose Biomedical AI Agent"
PROJECT_ENGINE = "Biomni"
PROJECT_ENGINE_VERSION = "0.0.8"
PROJECT_LICENSE = "Apache-2.0"

# ── UI Theme ───────────────────────────────────────────────
# ProtChat-inspired design tokens
THEME = {
    "primary_color": "#4f46e5",       # Indigo accent
    "primary_hover": "#4338ca",
    "background": "#f7f8fb",          # Soft light gray
    "sidebar_bg": "#fbfcfd",
    "card_bg": "#ffffff",
    "text_primary": "#20242c",
    "text_secondary": "#5a616d",
    "text_muted": "#8b919e",
    "border": "rgba(32, 36, 44, 0.08)",
    "border_radius": "14px",
    "font_family": "'Noto Sans SC', system-ui, -apple-system, sans-serif",
    "font_mono": "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Monaco, Consolas, monospace",

    # Status colors
    "green": "#16a34a",
    "amber": "#f59e0b",
    "red": "#dc2626",
    "border_solid": "#e5e7eb",
}

# ── Capability Registry ────────────────────────────────────
# Biochat's tool capabilities organized by domain
CAPABILITIES = {
    "biochemistry": {
        "name": "Biochemistry",
        "icon": "🔬",
        "description": "Protein & enzyme analysis, binding affinity",
    },
    "genomics": {
        "name": "Genomics",
        "icon": "🧬",
        "description": "Variant annotation, GWAS, sequence analysis",
    },
    "pharmacology": {
        "name": "Pharmacology",
        "icon": "💊",
        "description": "ADMET prediction, drug interactions, target ID",
    },
    "cell_biology": {
        "name": "Cell Biology",
        "icon": "🧫",
        "description": "scRNA-seq, pathway analysis, cell types",
    },
    "microbiology": {
        "name": "Microbiology",
        "icon": "🦠",
        "description": "Pathogen genomics, AMR, microbiome",
    },
    "immunology": {
        "name": "Immunology",
        "icon": "🛡️",
        "description": "Epitope prediction, TCR/BCR analysis",
    },
    "cancer_biology": {
        "name": "Cancer Biology",
        "icon": "🔬",
        "description": "Variant analysis, driver genes, tumor evolution",
    },
    "systems_biology": {
        "name": "Systems Biology",
        "icon": "🔗",
        "description": "Metabolic modeling, network analysis",
    },
    "literature": {
        "name": "Literature Mining",
        "icon": "📚",
        "description": "PubMed, bioRxiv search & extraction",
    },
    "databases": {
        "name": "30+ Databases",
        "icon": "🗄️",
        "description": "UniProt, Ensembl, PDB, ClinVar, KEGG…",
    },
}

# ── Safety Policy ──────────────────────────────────────────
SAFETY_POLICY = {
    "code_execution_warning": True,
    "requires_sandbox": True,
    "commercial_mode_supported": True,
    "academic_datasets_available": True,
    "default_timeout_seconds": 600,
    "max_timeout_seconds": 3600,
}

# ── Quick Actions ──────────────────────────────────────────
QUICK_ACTIONS = [
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

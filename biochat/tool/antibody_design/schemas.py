"""Phase 3A/3B constants — penalty table, safety disclaimer, provenance labels."""

SAFETY_DISCLAIMER = (
    "⚠️ 安全声明：本结果由AI辅助计算生成，未经湿实验验证。"
    "所有评分均为计算方法估算值，不代表实验结合亲和力或生物学活性。"
    "不可作为临床诊断、治疗决策或药物申报依据。"
)

PENALTY_TABLE = {
    # ── HARD EXCLUDE ────────────────────────────────────────
    "contains_cysteine":             ("HARD_EXCLUDE", 0, "Cysteine in CDRH3 causes disulfide bond risk"),
    "contains_stop_codon":           ("HARD_EXCLUDE", 0, "Stop codon in sequence"),
    "too_short":                     ("HARD_EXCLUDE", 0, "CDRH3 < 6 amino acids"),
    "too_long":                      ("HARD_EXCLUDE", 0, "CDRH3 > 32 amino acids"),
    "excessive_single_aa":           ("HARD_EXCLUDE", 0, "Single amino acid > 35%"),
    "poly_run":                      ("HARD_EXCLUDE", 0, "≥4 consecutive identical amino acids"),
    "contains_full_epitope_subsequence": ("HARD_EXCLUDE", 0, "CDRH3 contains full epitope — self-targeting"),

    # ── SOFT PENALTY ────────────────────────────────────────
    "cdrh3_length_outside_preferred_window": ("SOFT_PENALTY", 12, "CDRH3 length outside 13-16aa"),
    "excessive_aromatic":            ("SOFT_PENALTY", 15, "Aromatic fraction > 45%"),
    "high_aromatic_fraction":        ("SOFT_PENALTY", 15, "Aromatic fraction > 45%"),
    "excessive_gp":                  ("SOFT_PENALTY", 10, "Gly+Pro > 50%"),
    "possible_electrostatic_repulsion": ("SOFT_PENALTY", 8, "Electrostatic repulsion with epitope"),
    "missing_basic_residue_for_acidic_epitope": ("SOFT_PENALTY", 10, "No basic residue for acidic epitope"),
    "missing_acidic_residue_for_basic_epitope": ("SOFT_PENALTY", 10, "No acidic residue for basic epitope"),
    "contains_long_epitope_subsequence": ("SOFT_PENALTY", 20, "CDRH3 contains ≥4aa epitope substring"),

    # ── WARNING ─────────────────────────────────────────────
    "single_cys_in_vh":              ("WARNING", 5, "Cysteine in full VH"),
    "atypical_length":               ("WARNING", 3, "Unusual CDRH3 length"),
    "low_complexity":                ("WARNING", 2, "Low sequence complexity"),
    "hydrophobic_aromatic_cluster":  ("WARNING", 2, "Hydrophobic/aromatic cluster"),
}

PROVENANCE_LABELS = ("computed", "model_inferred", "heuristic", "llm_estimated")

VALID_AAS = set("ACDEFGHIKLMNPQRSTVWY")

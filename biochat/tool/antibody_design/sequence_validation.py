"""序列完整性校验模块 - 所有抗体序列分析的入口校验。

Usage:
    from biochat.tool.antibody_design.sequence_validation import clean_sequence, validate_vh_complete, classify_antibody_type
"""

VALID_AAS = set("ACDEFGHIKLMNPQRSTVWY")
VHH_FR2_MOTIFS = ["GWWRQ", "EREA", "EREG", "EREF", "GLVW"]
VH_FR4_MOTIFS = ["WGQG", "WGQGT"]
VL_FR4_MOTIFS = ["FGQG", "FGQGT", "FGGGT"]


def clean_sequence(seq: str) -> str:
    """去除空白、换行、转大写。"""
    return (seq or "").replace(" ", "").replace("\n", "").replace("\r", "").upper()


def validate_amino_acids(seq: str) -> None:
    """检查是否仅含 20 种标准氨基酸。非法字符抛 ValueError。"""
    invalid = sorted(set(seq) - VALID_AAS)
    if invalid:
        raise ValueError(f"非法氨基酸字符: {''.join(invalid)}")


def validate_vh_complete(seq: str) -> None:
    """VH 必须含 FR4 (WGQG 基序)。不满则抛 ValueError。"""
    seq = clean_sequence(seq)
    validate_amino_acids(seq)
    if not any(m in seq for m in VH_FR4_MOTIFS):
        raise ValueError("VH 不完整：缺少 FR4 (WGQG 基序)")


def validate_vl_complete(seq: str) -> None:
    """VL 必须含 FR4 (FGQG/FGQGT/FGGGT 基序)。"""
    seq = clean_sequence(seq)
    validate_amino_acids(seq)
    if not any(m in seq for m in VL_FR4_MOTIFS):
        raise ValueError("VL 不完整：缺少 FR4")


def detect_truncated_vh(seq: str) -> bool:
    """检测 VH 是否以 CAR/CAS/CAG/CAK 结尾但无 FR4。

    Returns True if truncated (incomplete).
    """
    seq = clean_sequence(seq)
    # 找最后一个疑似 CDRH3 起始
    for motif in ("CAR", "CAS", "CAG", "CAK", "CTR", "CVR", "CSR"):
        idx = seq.rfind(motif)
        if idx < 0:
            continue
        after = seq[idx + len(motif):]
        # 检查之后是否还有 FR4
        has_fr4 = any(m in after for m in VH_FR4_MOTIFS)
        if not has_fr4 and len(after) < 50:
            return True
    return False


def detect_vhh_motifs(seq: str) -> dict:
    """检测 VHH FR2 特征基序。

    Returns dict with keys: is_vhh (bool), motifs_found (list[str]).
    """
    seq = clean_sequence(seq)
    found = [m for m in VHH_FR2_MOTIFS if m in seq]
    return {"is_vhh": len(found) > 0, "motifs_found": found}


def classify_antibody_type(vh: str, vl: str | None = None) -> str:
    """分类抗体类型。

    Returns:
        "vhh" — 纳米抗体单域
        "standard_vhvl" — 标准双链 (VH+VL 完整)
        "incomplete_vh" — VH 残缺
        "incomplete_vl" — VH 完整但 VL 缺失/残缺
        "unknown" — 无法分类
    """
    vh = clean_sequence(vh)
    try:
        validate_amino_acids(vh)
    except ValueError:
        return "unknown"

    # 检查 VHH
    vhh_info = detect_vhh_motifs(vh)
    if vhh_info["is_vhh"]:
        return "vhh"

    # 检查 VH 完整性
    try:
        validate_vh_complete(vh)
        vh_ok = True
    except ValueError:
        vh_ok = False

    if not vh_ok or detect_truncated_vh(vh):
        return "incomplete_vh"

    # 检查 VL
    if vl is None or not vl.strip():
        return "incomplete_vl"

    try:
        validate_vl_complete(clean_sequence(vl))
        return "standard_vhvl"
    except ValueError:
        return "incomplete_vl"

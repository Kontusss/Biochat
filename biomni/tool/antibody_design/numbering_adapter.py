"""DEPRECATED: ANARCI 未安装，所有函数 raise NotImplementedError。"""
"""抗体编号适配器

当前环境无 ANARCI/AbNumber 等编号工具。
所有函数返回 NotImplementedError 或 status="unavailable"。
"""

from typing import Dict, List


def run_numbering_or_raise(seq: str, scheme: str = "imgt") -> Dict:
    """对抗体序列进行编号。

    Raises NotImplementedError because no numbering tool is installed.
    """
    raise NotImplementedError(
        "编号工具 (ANARCI/AbNumber) 未安装。"
        f"无法对序列进行 {scheme.upper()} 编号。"
        "请安装 ANARCI (`pip install anarci`) 后重试，"
        "或标注所有位点声明为 [HYPOTHESIS] 并禁止自动突变。"
    )


def get_position_residue(numbering_result, position: int) -> str:
    """从编号结果中获取指定位点的残基。

    numbering_result 必须来自 run_numbering_or_raise() 的成功输出。
    """
    raise NotImplementedError("编号工具不可用，无法查询位点残基。")


def require_numbering_for_position_claims(claims: List[Dict]) -> None:
    """检查突变声明是否依赖编号工具。

    如果 claims 中包含 Kabat/IMGT 位点引用且编号工具不可用，抛错。
    """
    for claim in claims:
        if claim.get("scheme") in ("kabat", "imgt", "chothia"):
            raise NotImplementedError(
                f"突变声明使用了 {claim['scheme']} 编号但编号工具不可用。"
                "位点特异性突变必须通过编号工具确认。"
                "请在安装 ANARCI 后重试，或将声明标记为 [HYPOTHESIS]。"
            )

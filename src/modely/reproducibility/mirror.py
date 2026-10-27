"""Mirror verification implementation."""

from __future__ import annotations

import json

from .comparison import compare_resources


def verify_mirror(left: str, right: str, *, token=None, deep: bool = True, compare_resources_func=None) -> dict:
    """Verify whether two resources appear to be equivalent mirrors."""
    if compare_resources_func is None:
        compare_resources_func = compare_resources
    comparison = compare_resources_func(left, right, token=token, include_files=True, include_card=True, include_formats=True, deep=deep)
    files = comparison.summary.get("files") or {}
    card = comparison.summary.get("card") or {}
    formats = comparison.summary.get("formats") or {}
    drift_reasons = []
    if files.get("added_files"):
        drift_reasons.append("right has extra files")
    if files.get("removed_files"):
        drift_reasons.append("right is missing files")
    if files.get("changed_size_files"):
        drift_reasons.append("common files differ")
    if card.get("license_changed"):
        drift_reasons.append("license differs")
    if formats.get("format_delta"):
        drift_reasons.append("weight formats differ")
    confidence = _mirror_confidence(files, card, formats, drift_reasons)
    if drift_reasons:
        status = "drifted"
    elif confidence >= 0.85:
        status = "ok"
    elif confidence >= 0.6:
        status = "likely"
    else:
        status = "uncertain"
    return {
        "status": status,
        "confidence": confidence,
        "evidence": {"files": files, "card": card, "formats": formats},
        "left": left,
        "right": right,
        "reasons": drift_reasons,
        "comparison": comparison.to_dict(),
        "recommendations": _mirror_recommendations(drift_reasons),
    }


def print_mirror_verification(result: dict, *, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    print(f"Mirror status: {result['status']}")
    print(f"Left:          {result['left']}")
    print(f"Right:         {result['right']}")
    if result["reasons"]:
        print("Drift reasons:")
        for reason in result["reasons"]:
            print(f"  - {reason}")
    for rec in result.get("recommendations") or []:
        print(f"Recommendation: {rec}")


def _mirror_confidence(files: dict, card: dict, formats: dict, reasons: list[str]) -> float:
    if reasons:
        return 0.2
    score = 0.4
    overlap = files.get("path_overlap_ratio")
    if overlap is not None:
        score += 0.3 * overlap
    if files.get("checksum_matches") or files.get("lfs_matches"):
        score += 0.2
    if formats and not formats.get("format_delta"):
        score += 0.1
    if card and not card.get("license_changed"):
        score += 0.05
    return round(min(score, 1.0), 3)


def _mirror_recommendations(reasons: list[str]) -> list[str]:
    if not reasons:
        return ["resources appear mirror-equivalent by selected checks"]
    return ["review differences before treating these resources as interchangeable"]


__all__ = [name for name in globals() if not name.startswith("_")]

"""측정 발과 추천 라스트/신발 사이의 착화 여유 평가."""
from __future__ import annotations

import numpy as np

from ..meshutil import smooth_profile


FIT_TARGETS = {
    "running": 5.0,
    "everyday": 4.0,
    "dress": 2.5,
    "snug": 2.0,
}


def _last_half_width_mm(lp: dict, u: float, design_profile: dict | None = None) -> float:
    design = design_profile or {}
    bw = lp["last_ball_width_mm"] + design.get("toe_extra_width_mm", 0.0)
    hw = lp["last_heel_width_mm"]
    half = smooth_profile(
        np.asarray([u], dtype=np.float64),
        [0.0, 0.05, 0.15, 0.45, 0.62, 0.72, 0.9, 0.985, 1.0],
        [0.12 * hw, 0.44 * hw, 0.5 * hw, 0.45 * bw, 0.49 * bw, 0.5 * bw,
         0.44 * bw, 0.24 * bw, 0.04 * bw],
    )[0]
    return float(half)


def _status(clearance: float, target: float) -> str:
    if clearance < 0:
        return "tight"
    if clearance < target:
        return "watch"
    return "ok"


def assess_fit(meas: dict, lp: dict, fit: str = "everyday", design_profile: dict | None = None) -> dict:
    """새끼발가락/토박스 중심의 신발 적합도 평가."""
    design = design_profile or {}
    target = FIT_TARGETS.get(fit, FIT_TARGETS["everyday"])
    toe = meas.get("toe_profile", {})

    ball_clearance = lp["last_ball_width_mm"] - meas["ball_width_mm"]
    pinky_zone_width = toe.get("pinky_zone_width_mm", meas["ball_width_mm"] * 0.72)
    pinky_last_width = 2.0 * _last_half_width_mm(lp, 0.84, design)
    lateral_relief = design.get("pinky_relief_mm", 0.0)
    pinky_clearance = pinky_last_width + lateral_relief - pinky_zone_width

    lateral_extent = toe.get("pinky_lateral_extent_mm", pinky_zone_width / 2.0)
    lateral_clearance = _last_half_width_mm(lp, 0.84, design) + lateral_relief - lateral_extent

    toe_tip_width = max(pinky_zone_width * 0.62, meas["ball_width_mm"] * 0.42)
    toe_tip_clearance = 2.0 * _last_half_width_mm(lp, 0.94, design) - toe_tip_width

    prominence = toe.get("pinky_lateral_prominence_mm", 0.0)
    risk_score = 0
    if lateral_clearance < target:
        risk_score += 2
    if pinky_clearance < target:
        risk_score += 1
    if toe_tip_clearance < target:
        risk_score += 1
    if prominence > 4.0:
        risk_score += 1
    if toe.get("toe_splay_ratio", 0.0) > 0.78:
        risk_score += 1

    if risk_score >= 4 or lateral_clearance < 0:
        verdict = "tight"
        label = "새끼발가락 압박 위험"
    elif risk_score >= 2:
        verdict = "watch"
        label = "새끼발가락 여유 주의"
    else:
        verdict = "ok"
        label = "새끼발가락 여유 양호"

    relief_needed = max(0.0, target - lateral_clearance)
    recommendations = []
    if relief_needed > 0:
        recommendations.append(f"외측 토박스 relief +{round(relief_needed + 1.5, 1)}mm 권장")
    if prominence > 4.0:
        recommendations.append("5번째 중족골/새끼발가락 돌출부 위 갑피를 soft lattice로 완화")
    if toe_tip_clearance < target:
        recommendations.append("발끝 테이퍼를 줄이고 전족부 flex groove를 앞쪽으로 이동")
    if not recommendations:
        recommendations.append("현재 추천 라스트 기준으로 새끼발가락 여유가 충분한 편")

    zones = [
        {
            "name": "발볼",
            "clearance_mm": round(ball_clearance, 1),
            "target_mm": target,
            "status": _status(ball_clearance, target),
        },
        {
            "name": "새끼발가락 라인",
            "clearance_mm": round(lateral_clearance, 1),
            "target_mm": target,
            "status": _status(lateral_clearance, target),
        },
        {
            "name": "앞코 테이퍼",
            "clearance_mm": round(toe_tip_clearance, 1),
            "target_mm": target,
            "status": _status(toe_tip_clearance, target),
        },
    ]

    return {
        "verdict": verdict,
        "label": label,
        "confidence": toe.get("confidence", 0.0),
        "target_clearance_mm": target,
        "pinky_clearance_mm": round(pinky_clearance, 1),
        "pinky_lateral_clearance_mm": round(lateral_clearance, 1),
        "toe_tip_clearance_mm": round(toe_tip_clearance, 1),
        "pinky_prominence_mm": round(prominence, 1),
        "recommended_pinky_relief_mm": round(relief_needed + 1.5, 1) if relief_needed > 0 else 0.0,
        "zones": zones,
        "recommendations": recommendations,
    }

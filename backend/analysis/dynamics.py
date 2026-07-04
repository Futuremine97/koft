"""보행 중 동적 편안함 추정 시뮬레이션."""
from __future__ import annotations


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(v)))


def _grade(score: float) -> str:
    if score >= 82:
        return "good"
    if score >= 68:
        return "watch"
    return "risk"


def simulate_dynamic_comfort(
    meas: dict,
    sizing: dict,
    fit_assessment: dict,
    design: dict,
    fit: str = "everyday",
    toe_reconstruction: dict | None = None,
) -> dict:
    """정적 치수/라스트/디자인으로 보행 단계별 편안함을 추정한다."""
    detections = meas.get("detections", {})
    rotation = detections.get("rotation", {})
    hallux = detections.get("hallux_valgus", {})
    toe_profile = meas.get("toe_profile", {})
    mesh_params = design.get("mesh_params", {})
    toe_recon = toe_reconstruction or {}

    rotation_angle = float(rotation.get("angle_deg", 0.0))
    medial_bias = _clamp(rotation_angle / 16.0, -1.0, 1.0)
    lateral_bias = -medial_bias
    heel_stack = float(mesh_params.get("heel_stack_mm", 28.0))
    forefoot_stack = float(mesh_params.get("forefoot_stack_mm", 17.0))
    pinky_relief = float(mesh_params.get("pinky_relief_mm", 0.0))
    texture_depth = float(mesh_params.get("texture_depth_mm", 0.8))
    tread_depth = float(mesh_params.get("tread_depth_mm", 2.2))

    pinky_clearance = float(fit_assessment.get("pinky_lateral_clearance_mm", 0.0))
    pinky_prominence = float(fit_assessment.get(
        "pinky_prominence_mm",
        toe_profile.get("pinky_lateral_prominence_mm", 0.0),
    ))
    target_clearance = float(fit_assessment.get("target_clearance_mm", 4.0))
    toe_conf = float(toe_recon.get("confidence", toe_profile.get("confidence", 0.0)))

    arch_type = meas.get("arch_type", "normal")
    arch_penalty = 8.0 if arch_type == "flat" else 4.0 if arch_type == "high" else 0.0
    stability_bonus = 7.0 if "Stability" in design.get("design_name", "") else 0.0
    relief_bonus = min(9.0, pinky_relief * 0.9)

    cushioning_score = _clamp(58.0 + (heel_stack - 24.0) * 2.1 + (forefoot_stack - 14.0) * 1.2)
    stability_score = _clamp(78.0 - abs(rotation_angle) * 1.25 - arch_penalty + stability_bonus + tread_depth)
    flex_score = _clamp(86.0 - max(0.0, forefoot_stack - 18.0) * 1.7 - texture_depth * 1.2)
    toe_score = _clamp(74.0 + (pinky_clearance - target_clearance) * 4.2 - pinky_prominence * 2.4 + relief_bonus)
    hallux_score = _clamp(84.0 - (12.0 if hallux.get("present") else 0.0))

    lateral_shear = _clamp(
        38.0
        + max(0.0, lateral_bias) * 24.0
        + max(0.0, target_clearance - pinky_clearance) * 8.0
        + pinky_prominence * 2.8
        - pinky_relief * 2.1,
        0.0,
        100.0,
    )
    impact_peak = _clamp(88.0 - cushioning_score * 0.62 + max(0.0, abs(rotation_angle) - 8.0) * 1.4)
    rollover_score = _clamp((flex_score * 0.48) + (toe_score * 0.28) + (hallux_score * 0.24))
    overall = _clamp(
        cushioning_score * 0.22
        + stability_score * 0.24
        + flex_score * 0.18
        + toe_score * 0.24
        + hallux_score * 0.12
        - lateral_shear * 0.08
    )

    def pressure(base: float, medial: float, lateral: float, toe: float, pinky: float) -> dict:
        return {
            "heel": round(_clamp(base), 1),
            "medial": round(_clamp(medial + medial_bias * 10.0), 1),
            "lateral": round(_clamp(lateral + lateral_bias * 12.0), 1),
            "forefoot": round(_clamp(toe), 1),
            "fifth_toe": round(_clamp(pinky + lateral_shear * 0.28), 1),
        }

    phases = [
        {
            "id": "heel_strike",
            "label": "착지",
            "stance_percent": "0-12%",
            "comfort_score": round(_clamp(cushioning_score - impact_peak * 0.18), 1),
            "pressure": pressure(78, 30, 36, 12, 8),
            "note": "뒤꿈치 충격 흡수와 초반 흔들림",
        },
        {
            "id": "loading",
            "label": "하중 수용",
            "stance_percent": "12-30%",
            "comfort_score": round(_clamp((cushioning_score + stability_score) / 2 - abs(rotation_angle) * 0.45), 1),
            "pressure": pressure(58, 55, 48, 28, 18),
            "note": "아치 지지와 회내/회외 제어",
        },
        {
            "id": "midstance",
            "label": "중간 지지",
            "stance_percent": "30-55%",
            "comfort_score": round(_clamp(stability_score - arch_penalty * 0.35), 1),
            "pressure": pressure(26, 62, 56, 44, 30),
            "note": "체중 중심이 발 중앙을 지나는 구간",
        },
        {
            "id": "terminal",
            "label": "뒤꿈치 들림",
            "stance_percent": "55-80%",
            "comfort_score": round(_clamp((flex_score + toe_score) / 2 - lateral_shear * 0.12), 1),
            "pressure": pressure(10, 48, 60, 76, 54),
            "note": "앞볼 굴곡과 새끼발가락 외측 마찰",
        },
        {
            "id": "toe_off",
            "label": "밀어내기",
            "stance_percent": "80-100%",
            "comfort_score": round(_clamp(rollover_score - lateral_shear * 0.10), 1),
            "pressure": pressure(4, 42, 54, 88, 62),
            "note": "엄지/발가락 추진과 앞코 여유",
        },
    ]

    notes = []
    if impact_peak > 42:
        notes.append("착지 충격이 큰 편이라 뒤꿈치/중족부 쿠셔닝을 더 부드럽게 조정 권장")
    if abs(rotation_angle) > 10:
        notes.append("회전 편향이 보행 안정성에 영향을 줄 수 있어 내외측 가이드 레일 조정 권장")
    if lateral_shear > 58:
        notes.append("새끼발가락 외측 전단 압력이 높아 추가 relief 또는 더 부드러운 갑피 권장")
    if flex_score < 72:
        notes.append("앞볼 굴곡이 다소 단단할 수 있어 flex groove를 깊게 조정 권장")
    if not notes:
        notes.append("보행 단계 전반에서 동적 편안함이 균형적인 편")

    return {
        "overall_score": round(overall, 1),
        "grade": _grade(overall),
        "confidence": round(min(0.94, max(0.35, toe_conf * 0.75 + fit_assessment.get("confidence", 0.0) * 0.25)), 2),
        "metrics": {
            "impact_peak": round(impact_peak, 1),
            "stability_score": round(stability_score, 1),
            "forefoot_flex_score": round(flex_score, 1),
            "pinky_shear_risk": round(lateral_shear, 1),
            "toe_off_score": round(rollover_score, 1),
        },
        "phases": phases,
        "notes": notes,
        "disclaimer": "정적 3D 재구성과 휴리스틱 보행 모델 기반 추정이며 실제 보행 센서/압력판 측정은 아닙니다.",
    }

"""측정치 → 사이즈/핏 추천 (inverse sizing)."""
from __future__ import annotations

import math


WIDTH_CLASSES = [  # (width_ratio 상한, 표기, 설명)
    (0.355, "B (좁음)", "표준보다 좁은 발볼"),
    (0.385, "D (표준)", "표준 발볼"),
    (0.410, "E (약간 넓음)", "표준보다 약간 넓은 발볼"),
    (0.435, "2E (넓음)", "넓은 발볼 — 와이드 핏 권장"),
    (9.999, "4E (매우 넓음)", "매우 넓은 발볼 — 와이드/커스텀 필수"),
]

FIT_ALLOWANCE = {  # 용도별 여유 공간 (mm)
    "running": 10.0,
    "everyday": 7.0,
    "dress": 5.0,
    "snug": 3.0,
}


def _kr_size(length_mm: float, allowance: float) -> int:
    return int(math.ceil((length_mm + allowance) / 5.0) * 5)


def _conversions(kr: int) -> dict:
    # 표준 근사 변환 (KR mm 기준): KR250=US7/EU40.5, KR270=US9/EU43.5
    us_m = round((kr - 180) / 10 * 2) / 2
    us_w = round(us_m + 1.5, 1)
    eu = round((kr * 0.15 + 3) * 2) / 2
    uk = round((us_m - 0.5) * 2) / 2
    return {"us_men": us_m, "us_women": us_w, "eu": eu, "uk": uk}


def recommend(meas: dict, fit: str = "everyday") -> dict:
    length = meas["foot_length_mm"]
    allowance = FIT_ALLOWANCE.get(fit, 7.0)
    kr = _kr_size(length, allowance)

    wr = meas["width_ratio"]
    width_label, width_desc = "D (표준)", "표준 발볼"
    for limit, label, desc in WIDTH_CLASSES:
        if wr <= limit:
            width_label, width_desc = label, desc
            break

    notes = []
    if meas["arch_type"] == "flat":
        notes.append("아치가 낮은 편 — 아치 서포트가 있는 인솔/모션컨트롤 계열 권장")
    elif meas["arch_type"] == "high":
        notes.append("아치가 높은 편 — 쿠셔닝이 좋은 뉴트럴 계열 + 아치 필러 권장")
    hb = meas["heel_width_mm"] / max(meas["ball_width_mm"], 1e-6)
    if hb < 0.68:
        notes.append("뒤꿈치가 볼 대비 좁음 — 힐컵이 타이트한 모델 또는 힐락 레이싱 권장")
    elif hb > 0.8:
        notes.append("뒤꿈치가 넓은 편 — 힐 여유가 있는 라스트 권장")
    if meas["instep_height_mm"] / max(length, 1e-6) > 0.29:
        notes.append("발등이 높은 편 — 발등 여유가 있는 디자인/끈 조절 권장")

    detections = meas.get("detections", {})
    rotation = detections.get("rotation", {})
    if rotation.get("type") == "inward":
        notes.append("내회전/회내 경향 — 내측 아치 지지와 안정성이 있는 라스트 권장")
    elif rotation.get("type") == "outward":
        notes.append("외회전/회외 경향 — 외측 충격 분산과 쿠셔닝 여유 권장")

    hallux = detections.get("hallux_valgus", {})
    if hallux.get("present"):
        notes.append("무지외반 경향 — 토박스 내측 여유와 엄지 압박이 적은 설계 권장")

    return {
        "fit_preference": fit,
        "allowance_mm": allowance,
        "recommended": {"kr_mm": kr, **_conversions(kr)},
        "width_class": width_label,
        "width_desc": width_desc,
        "fit_notes": notes,
        "last_params": {  # inverse design에 넘길 라스트 파라미터
            "last_length_mm": round(length + allowance, 1),
            "last_ball_width_mm": round(meas["ball_width_mm"] + 4.0, 1),
            "last_heel_width_mm": round(meas["heel_width_mm"] + 3.0, 1),
            "last_instep_height_mm": round(meas["instep_height_mm"] + 3.0, 1),
            "toe_spring_mm": 12.0,
            "heel_pitch_mm": 20.0 if fit != "dress" else 25.0,
            "arch_support_mm": round(max(meas["arch_height_mm"] - 2.0, 3.0), 1),
        },
    }

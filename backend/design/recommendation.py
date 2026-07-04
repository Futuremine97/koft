"""측정치 기반 end-to-end 디자인 및 브랜드 참고 추천."""
from __future__ import annotations


BRAND_LIBRARY = [
    {
        "brand": "New Balance",
        "line": "Fresh Foam X 1080 / 880 / 860",
        "url": "https://www.newbalance.com/men/shoes/running/",
        "strengths": {"wide", "daily", "stability", "walking"},
        "base": 72,
        "why": "폭 옵션과 데일리 트레이너 선택지가 넓어 발볼/사이즈 매칭에 유리",
        "fit_tip": "2E 이상이면 New Balance 폭 옵션을 우선 확인",
    },
    {
        "brand": "ASICS",
        "line": "GEL-KAYANO / GT-2000 / GEL-NIMBUS",
        "url": "https://www.asics.com/us/en-us/mens-running-shoes/c/aa10200000/",
        "strengths": {"stability", "flat_arch", "daily", "walking"},
        "base": 70,
        "why": "안정화 러닝화 계열이 강해 회내/낮은 아치 보정 참고에 좋음",
        "fit_tip": "내회전 경향이면 안정화 계열, 높은 아치면 쿠셔닝 계열 비교",
    },
    {
        "brand": "Brooks",
        "line": "Adrenaline GTS / Glycerin GTS / Ghost",
        "url": "https://www.brooksrunning.com/en_us/mens/shoes/road-running-shoes/",
        "strengths": {"stability", "daily", "walking", "orthotic"},
        "base": 68,
        "why": "가이드형 안정성 계열과 데일리 쿠셔닝 계열 비교가 쉬움",
        "fit_tip": "회내가 있거나 인솔을 넣을 계획이면 GTS/넉넉한 갑피 계열 확인",
    },
    {
        "brand": "HOKA",
        "line": "Bondi / Clifton / Arahi / Gaviota",
        "url": "https://www.hoka.com/en/us/",
        "strengths": {"cushion", "rocker", "high_arch", "walking"},
        "base": 67,
        "why": "두꺼운 쿠셔닝과 로커형 솔 참고에 좋아 회외/충격 흡수 설계에 유리",
        "fit_tip": "외회전/회외 경향이면 외측 충격 흡수와 로커 감각을 비교",
    },
    {
        "brand": "Nike",
        "line": "Structure / Vomero / Pegasus",
        "url": "https://www.nike.com/w/mens-running-shoes-37v7jznik1zy7ok",
        "strengths": {"daily", "stability", "responsive"},
        "base": 64,
        "why": "데일리 러닝, 반응성 쿠셔닝, 안정화 라인의 밸런스 참고에 적합",
        "fit_tip": "발볼이 매우 넓으면 실제 착화 폭을 꼭 확인",
    },
    {
        "brand": "Altra",
        "line": "Torin / Paradigm / Experience",
        "url": "https://www.altrarunning.com/",
        "strengths": {"toe_room", "wide", "hallux"},
        "base": 62,
        "why": "넓은 전족부와 엄지 압박 완화 콘셉트 참고에 좋음",
        "fit_tip": "무지외반 경향이면 토박스 형상을 비교",
    },
]


def _tag_context(meas: dict, sizing: dict, fit: str) -> set[str]:
    tags = {"daily"}
    detections = meas.get("detections", {})
    rotation = detections.get("rotation", {})
    hallux = detections.get("hallux_valgus", {})

    if "2E" in sizing.get("width_class", "") or "4E" in sizing.get("width_class", ""):
        tags.add("wide")
    if meas.get("arch_type") == "flat" or rotation.get("type") == "inward":
        tags.update({"stability", "flat_arch"})
    if meas.get("arch_type") == "high" or rotation.get("type") == "outward":
        tags.update({"cushion", "high_arch", "rocker"})
    if hallux.get("present"):
        tags.update({"hallux", "toe_room"})
    if fit in {"everyday", "snug"}:
        tags.add("walking")
    if fit == "running":
        tags.add("responsive")
    return tags


def recommend_design(
    meas: dict,
    sizing: dict,
    fit: str = "everyday",
    fit_assessment: dict | None = None,
) -> dict:
    """소재/텍스처/프린트 파라미터와 브랜드 참고 리스트를 반환."""
    tags = _tag_context(meas, sizing, fit)
    detections = meas.get("detections", {})
    rotation = detections.get("rotation", {})
    hallux = detections.get("hallux_valgus", {})
    pinky_fit = fit_assessment or {}
    width_class = sizing.get("width_class", "")
    pinky_risk = pinky_fit.get("verdict") in {"watch", "tight"}

    stability = "stability" in tags
    cushion = "cushion" in tags
    wide = "wide" in tags or hallux.get("present") or pinky_risk

    if pinky_fit.get("verdict") == "tight":
        design_name = "Pinky Relief Fit Shell"
        silhouette = "새끼발가락 외측 압박을 줄인 비대칭 relief 토박스 슈즈"
        texture = "lateral relief lattice"
        outsole = "lateral flex pods"
    elif stability:
        design_name = "Guided Stability Shell"
        silhouette = "낮은 내측 변형을 잡아주는 안정형 데일리 러너"
        texture = "medial-flow ribs"
        outsole = "wide chevron lugs"
    elif cushion:
        design_name = "Cushion Rocker Trainer"
        silhouette = "충격 흡수와 부드러운 전방 롤링을 우선한 쿠셔닝 러너"
        texture = "wave lattice"
        outsole = "segmented rocker pods"
    elif wide:
        design_name = "Relief Toe-Box Walker"
        silhouette = "전족부 압박을 줄인 와이드 토박스 워킹/데일리 슈즈"
        texture = "soft grid relief"
        outsole = "flex groove pods"
    else:
        design_name = "Balanced Everyday Runner"
        silhouette = "중립 착화에 맞춘 경량 데일리 러너"
        texture = "woven micro-rib"
        outsole = "balanced road lugs"

    toe_extra = 3.0 if wide else 0.0
    pinky_relief = max(
        0.0,
        pinky_fit.get("recommended_pinky_relief_mm", 0.0),
        3.0 if pinky_fit.get("verdict") == "watch" else 0.0,
    )
    upper_thickness = 3.6 if fit == "running" else 4.2
    heel_stack = 32.0 if cushion else 29.0 if stability else 27.0
    forefoot_stack = 20.0 if cushion else 17.0
    sole_margin = 8.0 if wide else 7.0 if stability else 6.0
    texture_depth = 1.1 if texture != "woven micro-rib" else 0.7

    materials = {
        "upper": "TPU 95A flexible lattice shell with breathable knit liner",
        "midsole": "TPU 90A lattice or SLS TPU foam-like infill",
        "outsole": "TPU 98A high-wear tread skin",
        "insole": "EVA/TPU custom arch insert",
    }
    if hallux.get("present") or pinky_risk:
        materials["upper"] = "soft TPU 95A relief shell with stretch mesh forefoot liner"
    if cushion:
        materials["midsole"] = "TPU 85A energy lattice with softer heel crash pad"

    print_profile = {
        "recommended_process": "SLS TPU for best one-piece flexibility; FDM TPU 95A for local prototyping",
        "layer_height_mm": 0.2,
        "wall_loops": 3,
        "infill": "gyroid 18-28%, denser under heel and medial/lateral rails",
        "support": "minimal organic supports; print shoe angled 12-18 degrees from sole plane",
        "post_process": "tumble/de-powder, heat set, then add lace/liner hardware",
        "note": "STL/OBJ에는 소재 정보가 저장되지 않으므로 이 프로파일을 제작 지시서로 함께 사용",
    }

    brand_recommendations = []
    for item in BRAND_LIBRARY:
        overlap = tags & item["strengths"]
        score = item["base"] + len(overlap) * 7
        if "wide" in overlap and "New Balance" == item["brand"]:
            score += 8
        if "hallux" in overlap and item["brand"] == "Altra":
            score += 10
        if "stability" in overlap and item["brand"] in {"ASICS", "Brooks"}:
            score += 7
        if "cushion" in overlap and item["brand"] == "HOKA":
            score += 8
        brand_recommendations.append({
            "brand": item["brand"],
            "line": item["line"],
            "score": min(score, 99),
            "why": item["why"],
            "fit_tip": item["fit_tip"],
            "url": item["url"],
        })
    brand_recommendations.sort(key=lambda x: x["score"], reverse=True)

    return {
        "design_name": design_name,
        "silhouette": silhouette,
        "material_stack": materials,
        "texture": {
            "upper": texture,
            "outsole": outsole,
            "toe_box": (
                f"lateral 5th-toe relief +{round(pinky_relief, 1)}mm"
                if pinky_relief else
                "extra anatomical toe relief" if wide else "standard anatomical toe taper"
            ),
            "ventilation": "open lattice over midfoot, denser heel counter",
        },
        "print_profile": print_profile,
        "mesh_params": {
            "upper_thickness_mm": upper_thickness,
            "heel_stack_mm": heel_stack,
            "forefoot_stack_mm": forefoot_stack,
            "sole_margin_mm": sole_margin,
            "texture_depth_mm": texture_depth,
            "toe_extra_width_mm": toe_extra,
            "pinky_relief_mm": pinky_relief,
            "pinky_side_sign": -1.0,
            "tread_depth_mm": 3.0 if fit == "running" else 2.2,
            "tread_count": 9 if fit == "running" else 7,
            "texture_kind": texture,
        },
        "design_rationale": [
            f"발볼 등급 {width_class}에 맞춰 라스트 여유와 토박스 relief를 조정",
            f"새끼발가락 핏: {pinky_fit.get('label', '기본 여유 평가 전')} 기준으로 외측 relief 반영",
            f"회전 감지: {rotation.get('label', '판정 불가')} 기준으로 안정/쿠셔닝 성향 반영",
            f"무지외반 스크리닝: {hallux.get('label', '판정 불가')} 기준으로 전족부 압박 완화 여부 반영",
        ],
        "brand_recommendations": brand_recommendations[:5],
    }

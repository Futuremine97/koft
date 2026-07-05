"""측정치 기반 end-to-end 디자인 및 브랜드 참고 추천."""
from __future__ import annotations


TEXTURE_LIBRARY = {
    "pinky_relief_lattice": {
        "name_ko": "새끼발가락 외측 릴리프 래티스",
        "upper": "asymmetric lateral relief lattice with soft woven base",
        "outsole": "lateral flex pods with pressure-release islands",
        "frequency_u": 38,
        "frequency_y": 135,
        "blend": "diamond_relief",
        "lug_style": "lateral_pods",
        "zones": [
            {"name": "새끼발가락 외측", "pattern": "확장형 다이아몬드 relief", "depth_mm": 1.35, "purpose": "마찰과 측면 압박 완화"},
            {"name": "토박스 상단", "pattern": "저밀도 breathable lattice", "depth_mm": 0.8, "purpose": "발가락 굴곡 시 압박 감소"},
            {"name": "중족부", "pattern": "micro woven support rib", "depth_mm": 0.55, "purpose": "갑피 늘어짐 억제"},
        ],
    },
    "medial_flow_ribs": {
        "name_ko": "내측 흐름 가이드 리브",
        "upper": "directional medial-flow ribs over knit micro texture",
        "outsole": "wide chevron traction with medial guidance rail",
        "frequency_u": 30,
        "frequency_y": 96,
        "blend": "flow_rib",
        "lug_style": "chevron",
        "zones": [
            {"name": "내측 아치", "pattern": "전후방 flow rib", "depth_mm": 1.25, "purpose": "내회전/낮은 아치 안정화"},
            {"name": "힐 카운터", "pattern": "조밀한 vertical rib", "depth_mm": 0.95, "purpose": "뒤꿈치 흔들림 감소"},
            {"name": "외측 전족부", "pattern": "얕은 flex mesh", "depth_mm": 0.55, "purpose": "과도한 강성 방지"},
        ],
    },
    "wave_lattice": {
        "name_ko": "로커 웨이브 래티스",
        "upper": "wave lattice gradient with soft heel-to-toe flow",
        "outsole": "segmented rocker pods with wave traction",
        "frequency_u": 26,
        "frequency_y": 82,
        "blend": "wave_lattice",
        "lug_style": "segmented_rocker",
        "zones": [
            {"name": "전족부", "pattern": "굴곡 방향 wave groove", "depth_mm": 1.05, "purpose": "toe-off 롤링 보조"},
            {"name": "뒤꿈치", "pattern": "충격 분산 ripple", "depth_mm": 0.9, "purpose": "착지 충격 시각/기능 표현"},
            {"name": "중족부", "pattern": "open wave lattice", "depth_mm": 0.75, "purpose": "통기성과 탄성 균형"},
        ],
    },
    "soft_grid_relief": {
        "name_ko": "와이드 토박스 소프트 그리드",
        "upper": "soft grid relief with anatomical toe-box expansion",
        "outsole": "flex groove pods under wide forefoot",
        "frequency_u": 34,
        "frequency_y": 118,
        "blend": "soft_grid",
        "lug_style": "flex_groove",
        "zones": [
            {"name": "와이드 토박스", "pattern": "큰 셀 soft grid", "depth_mm": 1.0, "purpose": "전족부 볼륨 여유 확보"},
            {"name": "발등", "pattern": "graded ventilation slot", "depth_mm": 0.65, "purpose": "압박감과 열감 완화"},
            {"name": "전족부 솔", "pattern": "가로 flex groove", "depth_mm": 1.2, "purpose": "넓은 발볼의 굴곡 보조"},
        ],
    },
    "woven_micro_rib": {
        "name_ko": "니트형 마이크로 리브",
        "upper": "woven micro-rib with subtle crosshatch texture",
        "outsole": "balanced road lugs with shallow siping",
        "frequency_u": 42,
        "frequency_y": 150,
        "blend": "woven",
        "lug_style": "balanced_road",
        "zones": [
            {"name": "갑피 전체", "pattern": "미세 crosshatch weave", "depth_mm": 0.7, "purpose": "가벼운 시각 질감과 TPU 출력 표면 보정"},
            {"name": "토박스", "pattern": "얕은 anatomical taper rib", "depth_mm": 0.55, "purpose": "중립 착화 유지"},
            {"name": "아웃솔", "pattern": "균형형 road siping", "depth_mm": 0.9, "purpose": "일상 보행 접지"},
        ],
    },
}


def _texture_system(texture_id: str, fit: str, pinky_relief: float) -> dict:
    spec = TEXTURE_LIBRARY[texture_id]
    zones = [dict(z) for z in spec["zones"]]
    if pinky_relief > 0:
        zones.append({
            "name": "5th toe custom relief window",
            "pattern": f"lateral expansion +{round(pinky_relief, 1)}mm",
            "depth_mm": 1.15,
            "purpose": "새끼발가락 돌출부 전용 공간 확보",
        })
    return {
        "id": texture_id,
        "name": spec["name_ko"],
        "upper_pattern": spec["upper"],
        "outsole_pattern": spec["outsole"],
        "zones": zones,
        "finish": {
            "upper_surface": "matte TPU micro-pebble finish",
            "edge_treatment": "0.6-0.9mm softened bevel on raised ribs",
            "colorway": "graphite base with mint functional highlights",
        },
        "manufacturing": {
            "min_feature_mm": 0.8 if fit == "running" else 0.7,
            "recommended_texture_depth_mm": max(z["depth_mm"] for z in zones),
            "print_note": "SLS TPU 권장. FDM TPU는 노즐 0.4mm 기준 리브/격자 간격 1.2mm 이상 유지",
        },
    }


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
        texture_id = "pinky_relief_lattice"
    elif stability:
        design_name = "Guided Stability Shell"
        silhouette = "낮은 내측 변형을 잡아주는 안정형 데일리 러너"
        texture_id = "medial_flow_ribs"
    elif cushion:
        design_name = "Cushion Rocker Trainer"
        silhouette = "충격 흡수와 부드러운 전방 롤링을 우선한 쿠셔닝 러너"
        texture_id = "wave_lattice"
    elif wide:
        design_name = "Relief Toe-Box Walker"
        silhouette = "전족부 압박을 줄인 와이드 토박스 워킹/데일리 슈즈"
        texture_id = "soft_grid_relief"
    else:
        design_name = "Balanced Everyday Runner"
        silhouette = "중립 착화에 맞춘 경량 데일리 러너"
        texture_id = "woven_micro_rib"

    texture_spec = TEXTURE_LIBRARY[texture_id]
    texture = texture_spec["upper"]
    outsole = texture_spec["outsole"]

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
    texture_depth = max(z["depth_mm"] for z in texture_spec["zones"])

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
        "texture_system": _texture_system(texture_id, fit, pinky_relief),
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
            "texture_preset": texture_id,
            "texture_frequency_u": texture_spec["frequency_u"],
            "texture_frequency_y": texture_spec["frequency_y"],
            "texture_blend": texture_spec["blend"],
            "lug_style": texture_spec["lug_style"],
        },
        "design_rationale": [
            f"발볼 등급 {width_class}에 맞춰 라스트 여유와 토박스 relief를 조정",
            f"새끼발가락 핏: {pinky_fit.get('label', '기본 여유 평가 전')} 기준으로 외측 relief 반영",
            f"회전 감지: {rotation.get('label', '판정 불가')} 기준으로 안정/쿠셔닝 성향 반영",
            f"무지외반 스크리닝: {hallux.get('label', '판정 불가')} 기준으로 전족부 압박 완화 여부 반영",
        ],
        "brand_recommendations": brand_recommendations[:5],
    }

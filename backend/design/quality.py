"""결과물의 제작/공개 준비 등급 산정."""
from __future__ import annotations


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(v)))


def _grade(score: float) -> tuple[str, str]:
    if score >= 90:
        return "A+", "프리미엄 제작 후보"
    if score >= 82:
        return "A", "공개 데모/샘플 제작 가능"
    if score >= 72:
        return "B+", "프로토타입 제작 가능"
    if score >= 62:
        return "B", "보정 후 제작 권장"
    return "C", "데이터 보강 필요"


def assess_artifact_quality(
    meas: dict,
    sizing: dict,
    fit_assessment: dict,
    design: dict,
    dynamic_simulation: dict,
    toe_reconstruction: dict,
    engine_used: str,
    lidar_used: bool,
) -> dict:
    """3D 프린팅/공개용 결과물의 완성도를 점수화한다."""
    toe_conf = float(toe_reconstruction.get("confidence", 0.0))
    fit_conf = float(fit_assessment.get("confidence", 0.0))
    dynamic_conf = float(dynamic_simulation.get("confidence", 0.0))
    dyn_score = float(dynamic_simulation.get("overall_score", 0.0))
    fit_verdict = fit_assessment.get("verdict", "unknown")
    mesh_params = design.get("mesh_params", {})
    print_profile = design.get("print_profile", {})

    data_score = 58.0 + toe_conf * 18.0 + fit_conf * 14.0 + dynamic_conf * 10.0
    if lidar_used:
        data_score += 6.0
    elif meas.get("scale_source") == "user_length":
        data_score += 4.0
    if engine_used == "vggt":
        data_score += 5.0

    fit_score = {
        "ok": 92.0,
        "watch": 78.0,
        "tight": 58.0,
    }.get(fit_verdict, 68.0)
    fit_score += min(6.0, float(mesh_params.get("pinky_relief_mm", 0.0)) * 0.8)

    print_score = 76.0
    if print_profile.get("recommended_process"):
        print_score += 8.0
    if mesh_params.get("tread_depth_mm") and mesh_params.get("upper_thickness_mm"):
        print_score += 8.0
    if design.get("material_stack"):
        print_score += 6.0

    score = _clamp(data_score * 0.26 + fit_score * 0.24 + dyn_score * 0.26 + print_score * 0.24)
    grade, label = _grade(score)

    checklist = [
        {
            "label": "발/발가락 재구성 신뢰",
            "status": "pass" if toe_conf >= 0.72 else "watch",
            "detail": f"발가락 평균 신뢰 {round(toe_conf * 100)}%",
        },
        {
            "label": "새끼발가락 신발 적합도",
            "status": "pass" if fit_verdict == "ok" else "watch" if fit_verdict == "watch" else "risk",
            "detail": fit_assessment.get("label", "판정 불가"),
        },
        {
            "label": "보행 동적 편안함",
            "status": "pass" if dyn_score >= 82 else "watch" if dyn_score >= 68 else "risk",
            "detail": f"동적 점수 {round(dyn_score, 1)}",
        },
        {
            "label": "3D 프린팅 제작 지시",
            "status": "pass" if print_score >= 88 else "watch",
            "detail": print_profile.get("recommended_process", "프린트 프로파일 보강 필요"),
        },
    ]

    notes = []
    if engine_used != "vggt":
        notes.append("데모 엔진 결과이므로 실제 발 사진 기반 정밀 제작 전 VGGT/LiDAR 재검증 권장")
    if not lidar_used:
        notes.append("절대 스케일 정확도를 높이려면 LiDAR 또는 실측 발 길이 입력 권장")
    if fit_verdict != "ok":
        notes.append("제작 전 토박스/새끼발가락 relief를 한 번 더 확인 권장")
    if score >= 82:
        notes.append("소재·텍스처·프린트 프로파일이 포함된 공개 데모용 결과물로 사용 가능")

    return {
        "score": round(score, 1),
        "grade": grade,
        "label": label,
        "readiness": "production_candidate" if score >= 82 else "prototype" if score >= 72 else "needs_refinement",
        "checklist": checklist,
        "notes": notes,
    }

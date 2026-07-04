"""정렬된 발 포인트클라우드에서 주요 측정치 추출 (단위: 미터 → mm 반환)."""
from __future__ import annotations

import numpy as np


def _extent(vals: np.ndarray, lo=0.005, hi=0.995) -> float:
    return float(np.quantile(vals, hi) - np.quantile(vals, lo))


def _width_at(pts: np.ndarray, x0: float, x1: float) -> float:
    sl = pts[(pts[:, 0] >= x0) & (pts[:, 0] <= x1)]
    if len(sl) < 20:
        return 0.0
    return _extent(sl[:, 1], 0.01, 0.99)


def _girth_at(pts: np.ndarray, x0: float, x1: float) -> float:
    """단면 둘레 근사: 폭·높이 타원 둘레(Ramanujan)."""
    sl = pts[(pts[:, 0] >= x0) & (pts[:, 0] <= x1)]
    if len(sl) < 20:
        return 0.0
    a = _extent(sl[:, 1], 0.01, 0.99) / 2
    b = float(np.quantile(sl[:, 2], 0.99)) / 2
    h = ((a - b) ** 2) / ((a + b) ** 2 + 1e-12)
    return float(np.pi * (a + b) * (1 + 3 * h / (10 + np.sqrt(4 - 3 * h))))


def _slice(pts: np.ndarray, L: float, x0: float, x1: float) -> np.ndarray:
    return pts[(pts[:, 0] >= x0 * L) & (pts[:, 0] <= x1 * L)]


def _edge(slice_pts: np.ndarray, side_sign: float, q: float = 0.985) -> float:
    if len(slice_pts) < 30:
        return 0.0
    return float(np.quantile(side_sign * slice_pts[:, 1], q))


def _level(score: float, mild: float, high: float) -> str:
    a = abs(score)
    if a >= high:
        return "high"
    if a >= mild:
        return "mild"
    return "normal"


def _rotation_detection(
    pts: np.ndarray,
    L: float,
    ball_width: float,
    arch_height: float,
    medial_sign: float,
    arch_delta: float,
) -> dict:
    """단일 3D 발 형상 기반 회내/회외성 롤 추정."""
    if L <= 0 or ball_width <= 0:
        return {
            "type": "unknown",
            "label": "판정 불가",
            "severity": "unknown",
            "angle_deg": 0.0,
            "confidence": 0.0,
            "note": "포인트가 부족해 회전 성향을 계산하지 못했습니다.",
        }

    zone = _slice(pts, L, 0.22, 0.72)
    band = max(ball_width * 0.14, 0.006)
    medial = zone[medial_sign * zone[:, 1] > band]
    lateral = zone[-medial_sign * zone[:, 1] > band]

    roll_deg = 0.0
    sample_conf = 0.0
    if len(medial) >= 40 and len(lateral) >= 40:
        medial_floor = float(np.quantile(medial[:, 2], 0.08))
        lateral_floor = float(np.quantile(lateral[:, 2], 0.08))
        # +값: 내측이 더 낮아지는 회내/내회전 경향, -값: 외측 하중/외회전 경향
        roll_deg = float(np.degrees(np.arctan2(lateral_floor - medial_floor, ball_width)))
        sample_conf = min(1.0, min(len(medial), len(lateral)) / 450.0)

    arch_ratio = arch_height / L if L else 0.0
    arch_component = float(np.clip((0.030 - arch_ratio) * 320.0, -9.0, 9.0))
    score = roll_deg + arch_component

    if score >= 7.0:
        label = "내회전 경향"
        rot_type = "inward"
    elif score <= -7.0:
        label = "외회전 경향"
        rot_type = "outward"
    else:
        label = "중립"
        rot_type = "neutral"

    confidence = 0.35 + 0.35 * sample_conf + 0.30 * min(1.0, arch_delta / max(0.012 * L, 1e-6))
    confidence = float(np.clip(confidence, 0.0, 0.95))

    return {
        "type": rot_type,
        "label": label,
        "severity": _level(score, 7.0, 12.0),
        "angle_deg": round(score, 1),
        "confidence": round(confidence, 2),
        "note": "내측/외측 바닥 높이와 아치 비율 기반 추정",
    }


def _hallux_candidate(pts: np.ndarray, L: float, side_sign: float) -> tuple[float, float]:
    mtp = _slice(pts, L, 0.62, 0.76)
    toe = _slice(pts, L, 0.86, 0.98)
    if len(mtp) < 50 or len(toe) < 50 or L <= 0:
        return 0.0, 0.0

    medial_taper = max(0.0, _edge(mtp, side_sign, 0.99) - _edge(toe, side_sign, 0.985))
    lateral_taper = max(0.0, _edge(mtp, -side_sign, 0.99) - _edge(toe, -side_sign, 0.985))
    excess = max(0.0, medial_taper - lateral_taper)
    dx = max(0.18 * L, 1e-6)
    angle = float(np.degrees(np.arctan2(excess, dx)))
    return angle, excess


def _hallux_detection(
    pts: np.ndarray,
    L: float,
    medial_sign: float,
    arch_delta: float,
) -> dict:
    """무지외반증 외곽선 스크리닝. 실제 HVA 진단은 X-ray/임상 평가가 필요."""
    if L <= 0:
        return {
            "present": False,
            "label": "판정 불가",
            "severity": "unknown",
            "angle_deg": 0.0,
            "confidence": 0.0,
            "note": "포인트가 부족해 무지외반 추정을 계산하지 못했습니다.",
        }

    angle, excess = _hallux_candidate(pts, L, medial_sign)
    opposite_angle, _ = _hallux_candidate(pts, L, -medial_sign)
    side_conf = min(1.0, arch_delta / max(0.012 * L, 1e-6))

    # 아치로 내측 판정이 불확실한 경우에는 양쪽 중 더 강한 돌출 후보를 쓰되,
    # 신뢰도를 낮춰 단일 발 스캔의 한계를 드러낸다.
    if side_conf < 0.35 and opposite_angle > angle + 3.0:
        angle = opposite_angle
        side_conf *= 0.7

    if angle >= 40.0:
        label, severity = "무지외반 의심 높음", "severe"
    elif angle >= 21.0:
        label, severity = "무지외반 의심", "moderate"
    elif angle >= 15.0:
        label, severity = "무지외반 경향", "mild"
    else:
        label, severity = "정상 범위", "normal"

    toe_sample = len(_slice(pts, L, 0.82, 0.99))
    sample_conf = min(1.0, toe_sample / 800.0)
    magnitude_conf = min(1.0, excess / max(0.018 * L, 1e-6))
    confidence = 0.25 + 0.30 * sample_conf + 0.25 * side_conf + 0.20 * magnitude_conf
    confidence = float(np.clip(confidence, 0.0, 0.92))

    return {
        "present": bool(angle >= 15.0),
        "label": label,
        "severity": severity,
        "angle_deg": round(angle, 1),
        "confidence": round(confidence, 2),
        "note": "전족부 내측 돌출과 엄지발가락 쪽 외곽선 기울기 기반 스크리닝",
    }


def _toe_profile(pts: np.ndarray, L: float, ball_width: float, medial_sign: float) -> dict:
    if L <= 0 or ball_width <= 0:
        return {
            "pinky_zone_width_mm": 0.0,
            "pinky_lateral_extent_mm": 0.0,
            "pinky_lateral_prominence_mm": 0.0,
            "pinky_toe_angle_deg": 0.0,
            "toe_splay_ratio": 0.0,
            "confidence": 0.0,
        }

    lateral_sign = -medial_sign
    ball = _slice(pts, L, 0.58, 0.75)
    pinky = _slice(pts, L, 0.76, 0.90)
    tip = _slice(pts, L, 0.90, 0.985)
    if len(ball) < 40 or len(pinky) < 40:
        return {
            "pinky_zone_width_mm": 0.0,
            "pinky_lateral_extent_mm": 0.0,
            "pinky_lateral_prominence_mm": 0.0,
            "pinky_toe_angle_deg": 0.0,
            "toe_splay_ratio": 0.0,
            "confidence": 0.0,
        }

    ball_lat = _edge(ball, lateral_sign, 0.985)
    pinky_lat = _edge(pinky, lateral_sign, 0.99)
    tip_lat = _edge(tip, lateral_sign, 0.985) if len(tip) >= 40 else pinky_lat * 0.72
    expected_lat = ball_lat * 0.58 + tip_lat * 0.42
    prominence = max(0.0, pinky_lat - expected_lat)
    pinky_width = _extent(pinky[:, 1], 0.01, 0.99)
    toe_splay_ratio = pinky_width / max(ball_width, 1e-6)
    angle = float(np.degrees(np.arctan2(prominence, max(0.14 * L, 1e-6))))
    confidence = min(0.95, min(len(pinky), len(ball)) / 700.0 + 0.25)

    mm = lambda v: round(v * 1000, 1)
    return {
        "pinky_zone_width_mm": mm(pinky_width),
        "pinky_lateral_extent_mm": mm(pinky_lat),
        "pinky_lateral_prominence_mm": mm(prominence),
        "pinky_toe_angle_deg": round(angle, 1),
        "toe_splay_ratio": round(toe_splay_ratio, 3),
        "confidence": round(confidence, 2),
    }


def measure(pts: np.ndarray) -> dict:
    """pts: align_foot 을 거친 (N,3), x=길이, y=폭(내측+), z=높이."""
    L = _extent(pts[:, 0])

    ball_zone = (0.58 * L, 0.75 * L)
    heel_zone = (0.02 * L, 0.18 * L)
    instep_zone = (0.40 * L, 0.55 * L)
    arch_zone = (0.35 * L, 0.60 * L)

    ball_width = _width_at(pts, *ball_zone)
    heel_width = _width_at(pts, *heel_zone)

    sl = pts[(pts[:, 0] >= instep_zone[0]) & (pts[:, 0] <= instep_zone[1])]
    instep_height = float(np.quantile(sl[:, 2], 0.99)) if len(sl) else 0.0

    # 아치 높이: 중족부 바닥면의 지면 이격. 좌/우발·정렬 부호에 무관하도록
    # 양쪽(y>0, y<0)을 모두 재고 더 높은 쪽을 내측(медial)로 판정.
    def _side_arch(sign: float) -> float:
        band = 0.15 * ball_width / 2
        a = pts[
            (pts[:, 0] >= arch_zone[0]) & (pts[:, 0] <= arch_zone[1])
            & (sign * pts[:, 1] > band)
        ]
        if len(a) < 30:
            return 0.0
        low = a[a[:, 2] < np.quantile(a[:, 2], 0.15)]
        return float(np.median(low[:, 2])) if len(low) else 0.0

    side_arch_pos = _side_arch(+1.0)
    side_arch_neg = _side_arch(-1.0)
    arch_height = max(side_arch_pos, side_arch_neg)
    medial_sign = 1.0 if side_arch_pos >= side_arch_neg else -1.0
    arch_delta = abs(side_arch_pos - side_arch_neg)

    ball_girth = _girth_at(pts, *ball_zone)
    instep_girth = _girth_at(pts, *instep_zone)

    ah_ratio = arch_height / L if L else 0
    if ah_ratio < 0.018:
        arch_type = "flat"       # 평발 경향
    elif ah_ratio > 0.045:
        arch_type = "high"       # 요족(높은 아치)
    else:
        arch_type = "normal"

    mm = lambda v: round(v * 1000, 1)
    detections = {
        "rotation": _rotation_detection(
            pts, L, ball_width, arch_height, medial_sign, arch_delta
        ),
        "hallux_valgus": _hallux_detection(pts, L, medial_sign, arch_delta),
    }
    toe_profile = _toe_profile(pts, L, ball_width, medial_sign)
    return {
        "foot_length_mm": mm(L),
        "ball_width_mm": mm(ball_width),
        "heel_width_mm": mm(heel_width),
        "instep_height_mm": mm(instep_height),
        "arch_height_mm": mm(arch_height),
        "ball_girth_mm": mm(ball_girth),
        "instep_girth_mm": mm(instep_girth),
        "width_ratio": round(ball_width / L, 3) if L else 0,
        "arch_type": arch_type,
        "medial_sign": medial_sign,
        "detections": detections,
        "toe_profile": toe_profile,
        "n_points": int(len(pts)),
    }

"""발가락별 3D 재구성: 엄지~새끼발가락 분리 메쉬와 측정치."""
from __future__ import annotations

import numpy as np

from ..meshutil import loft, merge, smooth_profile


TOE_LAYOUT = [
    ("hallux", "엄지", 0.30, 0.30, 0.250, 1.000, 1.00),
    ("second", "둘째", 0.11, 0.19, 0.255, 0.995, 0.88),
    ("third", "셋째", -0.04, 0.17, 0.225, 0.970, 0.78),
    ("fourth", "넷째", -0.18, 0.15, 0.195, 0.945, 0.70),
    ("fifth", "새끼", -0.31, 0.13, 0.165, 0.920, 0.62),
]


def _sample_confidence(pts: np.ndarray, x0: float, x1: float, y0: float, y1: float) -> tuple[float, int]:
    if len(pts) == 0:
        return 0.0, 0
    sl = pts[
        (pts[:, 0] >= x0) & (pts[:, 0] <= x1)
        & (pts[:, 1] >= y0) & (pts[:, 1] <= y1)
    ]
    count = len(sl)
    return round(float(np.clip(count / 240.0, 0.2, 0.96)), 2), count


def _toe_mesh(
    x0: float,
    x1: float,
    y0: float,
    width: float,
    height: float,
    floor_z: float,
    splay: float,
    n_sec: int = 18,
    n_around: int = 28,
):
    xs = np.linspace(x0, x1, n_sec)
    u = np.linspace(0.0, 1.0, n_sec)
    radius_profile = smooth_profile(
        u, [0.0, 0.10, 0.62, 0.88, 1.0], [0.78, 1.0, 0.92, 0.52, 0.12]
    )
    height_profile = smooth_profile(
        u, [0.0, 0.16, 0.65, 0.92, 1.0], [0.72, 1.0, 0.88, 0.45, 0.12]
    )
    t = np.linspace(0, 2 * np.pi, n_around, endpoint=False)
    sections = []
    for i, x in enumerate(xs):
        yn = y0 + splay * (u[i] - 0.35) ** 2
        ry = max(width * 0.5 * radius_profile[i], 0.001)
        rz = max(height * height_profile[i], 0.0015)
        y = yn + ry * np.cos(t)
        z = floor_z + rz * (0.5 + 0.5 * np.sin(t)) ** 0.72
        sections.append(np.stack([np.full_like(y, x), y, z], axis=1).astype(np.float32))
    return loft(sections)


def reconstruct_toes(pts: np.ndarray, meas: dict) -> tuple[tuple[np.ndarray, np.ndarray], dict]:
    """정렬된 포인트와 측정치로 발가락 5개를 분리 근사 재구성."""
    L = meas["foot_length_mm"] / 1000.0
    bw = meas["ball_width_mm"] / 1000.0
    instep_h = meas["instep_height_mm"] / 1000.0
    toe_profile = meas.get("toe_profile", {})
    medial_sign = float(meas.get("medial_sign", 1.0))
    pinky_prom = toe_profile.get("pinky_lateral_prominence_mm", 0.0) / 1000.0
    hallux = meas.get("detections", {}).get("hallux_valgus", {})
    hallux_angle = hallux.get("angle_deg", 0.0)

    floor_z = 0.001
    toe_h = max(instep_h * 0.34, L * 0.055)
    meshes = []
    toes = []
    for key, label, y_ratio, w_ratio, len_ratio, tip_ratio, h_ratio in TOE_LAYOUT:
        y_center = medial_sign * y_ratio * bw
        width = w_ratio * bw
        length = len_ratio * L
        tip_x = tip_ratio * L
        base_x = max(0.68 * L, tip_x - length)
        splay = 0.0
        if key == "fifth":
            width += pinky_prom * 0.55
            splay = -medial_sign * max(pinky_prom, 0.0015)
        elif key == "hallux" and hallux.get("present"):
            splay = -medial_sign * min(0.012, hallux_angle / 2200.0)

        mesh = _toe_mesh(base_x, tip_x, y_center, width, toe_h * h_ratio, floor_z, splay)
        meshes.append(mesh)
        conf, sample_count = _sample_confidence(
            pts,
            base_x,
            tip_x,
            y_center - width * 0.9,
            y_center + width * 0.9,
        )
        toes.append({
            "id": key,
            "label": label,
            "length_mm": round((tip_x - base_x) * 1000, 1),
            "width_mm": round(width * 1000, 1),
            "height_mm": round(toe_h * h_ratio * 1000, 1),
            "center_y_mm": round(y_center * 1000, 1),
            "sample_count": int(sample_count),
            "confidence": conf,
        })

    combined = merge(*meshes)
    confidence = round(sum(t["confidence"] for t in toes) / len(toes), 2)
    report = {
        "toes": toes,
        "confidence": confidence,
        "note": "사진/LiDAR 포인트의 전족부 범위와 발 치수를 결합한 발가락별 근사 재구성",
    }
    return combined, report

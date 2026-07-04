"""커스텀 인솔 — 발바닥 윤곽 + 개인 아치 서포트 + 힐컵."""
from __future__ import annotations

import numpy as np

from ..meshutil import loft, smooth_profile


def build_insole(meas: dict, lp: dict, n_sec: int = 70, n_around: int = 44):
    L = lp["last_length_mm"] / 1000.0
    bw = meas["ball_width_mm"] / 1000.0
    hw = meas["heel_width_mm"] / 1000.0
    arch = lp["arch_support_mm"] / 1000.0
    base_th = 0.004
    heel_cup = 0.008

    xs = np.linspace(0.0, L, n_sec)
    u = xs / L
    half_w = smooth_profile(
        u,
        [0.0, 0.05, 0.15, 0.45, 0.62, 0.72, 0.9, 0.985, 1.0],
        [0.2 * hw, 0.46 * hw, 0.5 * hw, 0.45 * bw, 0.49 * bw, 0.5 * bw,
         0.45 * bw, 0.3 * bw, 0.08 * bw],
    ) + 0.001
    arch_amp = smooth_profile(
        u, [0.0, 0.25, 0.42, 0.55, 0.7, 1.0], [0, 0.1, 1.0, 0.85, 0.05, 0]
    ) * arch
    cup_amp = smooth_profile(
        u, [0.0, 0.1, 0.22, 0.35, 1.0], [1.0, 0.9, 0.5, 0.0, 0.0]
    ) * heel_cup

    t = np.linspace(0, 2 * np.pi, n_around, endpoint=False)
    sections = []
    for i, x in enumerate(xs):
        y = half_w[i] * np.cos(t)
        s = np.sin(t)
        top = s > 0
        z = np.where(top, base_th, 0.0).astype(np.float64)
        yn = y / max(half_w[i], 1e-9)  # -1(외측)~+1(내측)
        # 내측 아치 서포트 (윗면만)
        medial = np.clip(yn, 0, 1) ** 1.5
        z += np.where(top, arch_amp[i] * medial, 0.0)
        # 힐컵: 가장자리 융기 (윗면만)
        rim = np.abs(yn) ** 3
        z += np.where(top, cup_amp[i] * rim, 0.0)
        # 에지 라운딩: 윗면 가장자리를 부드럽게
        sections.append(
            np.stack([np.full_like(y, x), y, z], axis=1).astype(np.float32)
        )
    return loft(sections)

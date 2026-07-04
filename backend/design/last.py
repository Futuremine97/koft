"""커스텀 라스트(신발골) 생성 — 측정치 기반 inverse design 1단계.

발 형상을 그대로 쓰지 않고 제화 규칙을 적용:
- 길이 = 발 길이 + 핏 여유
- 토 스프링(발끝 들림), 힐 피치(뒤꿈치 높이)
- 매끈한 단면 (발가락 요철 제거)
"""
from __future__ import annotations

import numpy as np

from ..meshutil import loft, smooth_profile


def build_last(lp: dict, n_sec: int = 70, n_around: int = 56):
    L = lp["last_length_mm"] / 1000.0
    bw = lp["last_ball_width_mm"] / 1000.0
    hw = lp["last_heel_width_mm"] / 1000.0
    ih = lp["last_instep_height_mm"] / 1000.0
    toe_spring = lp["toe_spring_mm"] / 1000.0
    heel_pitch = lp["heel_pitch_mm"] / 1000.0

    xs = np.linspace(0.0, L, n_sec)
    u = xs / L

    half_w = smooth_profile(
        u,
        [0.0, 0.05, 0.15, 0.45, 0.62, 0.72, 0.9, 0.985, 1.0],
        [0.12 * hw, 0.44 * hw, 0.5 * hw, 0.45 * bw, 0.49 * bw, 0.5 * bw,
         0.44 * bw, 0.24 * bw, 0.04 * bw],
    )
    top_h = smooth_profile(
        u,
        [0.0, 0.06, 0.22, 0.45, 0.6, 0.78, 0.94, 1.0],
        [0.6 * ih, 0.95 * ih, 1.0 * ih, 0.98 * ih, 0.82 * ih, 0.5 * ih,
         0.3 * ih, 0.12 * ih],
    )
    # 바닥 라인: 힐 피치 → 0 → 토 스프링
    bottom = smooth_profile(
        u,
        [0.0, 0.12, 0.35, 0.65, 0.85, 1.0],
        [heel_pitch, heel_pitch * 0.85, 0.0, 0.0, toe_spring * 0.4, toe_spring],
    )

    t = np.linspace(0, 2 * np.pi, n_around, endpoint=False)
    sections = []
    for i, x in enumerate(xs):
        y = half_w[i] * np.cos(t)
        s = 0.5 * (1 + np.sin(t))
        z = bottom[i] + top_h[i] * np.power(s, 0.78)
        sections.append(
            np.stack([np.full_like(y, x), y, z], axis=1).astype(np.float32)
        )
    return loft(sections)

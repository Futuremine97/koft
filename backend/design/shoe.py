"""커스텀 신발 메쉬 — 라스트에 갑피 두께 오프셋 + 밑창 결합."""
from __future__ import annotations

import numpy as np

from ..meshutil import loft, merge, offset_mesh, smooth_profile, vertex_normals
from .last import build_last


def _sole_profiles(lp: dict, xs: np.ndarray, design: dict):
    L = lp["last_length_mm"] / 1000.0
    bw = lp["last_ball_width_mm"] / 1000.0 + design.get("toe_extra_width_mm", 0.0) / 1000.0
    hw = lp["last_heel_width_mm"] / 1000.0
    margin = design.get("sole_margin_mm", 6.0) / 1000.0
    heel_th = design.get("heel_stack_mm", 28.0) / 1000.0
    toe_th = design.get("forefoot_stack_mm", 14.0) / 1000.0

    u = np.clip(xs / L, 0, 1)
    half_w = smooth_profile(
        u,
        [0.0, 0.05, 0.15, 0.45, 0.62, 0.72, 0.9, 1.0],
        [0.30 * hw, 0.46 * hw, 0.5 * hw, 0.46 * bw, 0.49 * bw, 0.5 * bw,
         0.45 * bw, 0.28 * bw],
    ) + margin
    thickness = smooth_profile(
        u, [0.0, 0.25, 0.6, 1.0], [heel_th, heel_th * 0.8, toe_th * 1.2, toe_th]
    )
    rocker = smooth_profile(  # 앞부분 로커(들림)
        u, [0.0, 0.7, 0.9, 1.0], [0.0, 0.0, 0.004, 0.010]
    )
    return half_w, thickness, rocker


def _sole(lp: dict, design_profile: dict | None = None, n_sec: int = 60, n_around: int = 40):
    design = design_profile or {}
    L = lp["last_length_mm"] / 1000.0
    xs = np.linspace(-0.008, L + 0.010, n_sec)
    half_w, thickness, rocker = _sole_profiles(lp, xs, design)

    t = np.linspace(0, 2 * np.pi, n_around, endpoint=False)
    sections = []
    for i, x in enumerate(xs):
        y = half_w[i] * np.cos(t)
        # 납작한 슬래브 단면 (라운드 에지)
        s = np.sin(t)
        z = rocker[i] + thickness[i] * 0.5 * (1 + np.clip(s * 1.4, -1, 1))
        z -= thickness[i]  # 윗면을 z=rocker 에 맞춤
        sections.append(
            np.stack([np.full_like(y, x), y, z + rocker[i] * 0], axis=1).astype(
                np.float32
            )
        )
    return loft(sections)


def _box_mesh(x0, x1, y0, y1, z0, z1):
    verts = np.asarray([
        [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
        [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1],
    ], dtype=np.float32)
    faces = np.asarray([
        [0, 1, 2], [0, 2, 3], [4, 6, 5], [4, 7, 6],
        [0, 4, 5], [0, 5, 1], [1, 5, 6], [1, 6, 2],
        [2, 6, 7], [2, 7, 3], [3, 7, 4], [3, 4, 0],
    ], dtype=np.int32)
    return verts, faces


def _tread_lugs(lp: dict, design: dict):
    depth = design.get("tread_depth_mm", 2.2) / 1000.0
    count = int(design.get("tread_count", 7))
    if depth <= 0 or count <= 0:
        return None

    L = lp["last_length_mm"] / 1000.0
    xs = np.linspace(0.10 * L, 0.92 * L, count)
    half_w, thickness, _ = _sole_profiles(lp, xs, design)
    lugs = []
    for i, x in enumerate(xs):
        lug_len = L * (0.035 if i % 2 else 0.045)
        lug_width = half_w[i] * (0.82 if i % 2 else 0.68)
        z_top = -thickness[i] + 0.001
        z_bot = z_top - depth
        lugs.append(_box_mesh(x - lug_len, x + lug_len, -lug_width, lug_width, z_bot, z_top))
    return merge(*lugs)


def _apply_upper_design(verts: np.ndarray, faces: np.ndarray, lp: dict, design: dict):
    out = verts.copy()
    L = lp["last_length_mm"] / 1000.0
    u = np.clip(out[:, 0] / L, 0, 1)

    toe_extra = design.get("toe_extra_width_mm", 0.0) / 1000.0
    if toe_extra > 0:
        toe_relief = np.clip((u - 0.58) / 0.36, 0, 1)
        out[:, 1] += np.sign(out[:, 1]) * toe_extra * toe_relief

    pinky_relief = design.get("pinky_relief_mm", 0.0) / 1000.0
    if pinky_relief > 0:
        side = float(design.get("pinky_side_sign", -1.0))
        forefoot = np.clip((u - 0.68) / 0.18, 0, 1) * np.clip((0.96 - u) / 0.18, 0, 1)
        lateral = np.clip(side * out[:, 1] / max(lp["last_ball_width_mm"] / 2000.0, 1e-6), 0, 1)
        out[:, 1] += side * pinky_relief * forefoot * lateral

    depth = design.get("texture_depth_mm", 0.0) / 1000.0
    if depth <= 0:
        return out

    normals = vertex_normals(out, faces)
    kind = design.get("texture_kind", "")
    y = out[:, 1]
    z = out[:, 2]
    if "grid" in kind:
        pattern = np.sin(u * np.pi * 34) * np.sin(y * 180)
        pattern = np.maximum(pattern, 0.0)
    elif "wave" in kind or "rocker" in kind:
        pattern = 0.5 + 0.5 * np.sin(u * np.pi * 24 + y * 65)
    else:
        pattern = 0.5 + 0.5 * np.sin(u * np.pi * 30 + np.abs(y) * 90)

    mask = (u > 0.08) & (u < 0.96) & (z > 0.010)
    out += normals * (depth * pattern * mask)[:, None]
    return out.astype(np.float32)


def build_shoe(lp: dict, upper_thickness_mm: float = 4.0, design_profile: dict | None = None):
    design = design_profile or {}
    upper_thickness_mm = design.get("upper_thickness_mm", upper_thickness_mm)
    last_v, last_f = build_last(lp)
    upper_v, upper_f = offset_mesh(last_v, last_f, upper_thickness_mm / 1000.0)
    upper_v = _apply_upper_design(upper_v, upper_f, lp, design)
    sole_v, sole_f = _sole(lp, design)
    # 갑피를 밑창 윗면 위로 올림
    upper_v = upper_v.copy()
    upper_v[:, 2] += 0.002
    tread = _tread_lugs(lp, design)
    if tread is None:
        return merge((upper_v, upper_f), (sole_v, sole_f))
    return merge((upper_v, upper_f), (sole_v, sole_f), tread)

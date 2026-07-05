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
    style = design.get("lug_style", "balanced_road")
    lugs = []
    for i, x in enumerate(xs):
        lug_len = L * (0.035 if i % 2 else 0.045)
        z_top = -thickness[i] + 0.001
        z_bot = z_top - depth
        if style == "chevron":
            lug_width = half_w[i] * 0.42
            offset = lug_len * 0.42
            lugs.append(_box_mesh(x - lug_len, x + offset, 0.004, lug_width, z_bot, z_top))
            lugs.append(_box_mesh(x - offset, x + lug_len, -lug_width, -0.004, z_bot, z_top))
        elif style == "segmented_rocker":
            lug_width = half_w[i] * 0.30
            for side in (-1, 0, 1):
                y0 = -lug_width * 0.48 if side == 0 else side * lug_width * 0.78
                lugs.append(_box_mesh(x - lug_len * 0.72, x + lug_len * 0.72,
                                      y0 - lug_width * 0.42, y0 + lug_width * 0.42, z_bot, z_top))
        elif style == "lateral_pods":
            medial_w = half_w[i] * 0.30
            lateral_w = half_w[i] * 0.46
            lugs.append(_box_mesh(x - lug_len * 0.8, x + lug_len * 0.8, 0.004, medial_w, z_bot, z_top))
            lugs.append(_box_mesh(x - lug_len, x + lug_len, -lateral_w, -0.006, z_bot - depth * 0.18, z_top))
        elif style == "flex_groove":
            lug_width = half_w[i] * 0.36
            lugs.append(_box_mesh(x - lug_len, x + lug_len, -half_w[i] * 0.78, -lug_width * 0.18, z_bot, z_top))
            lugs.append(_box_mesh(x - lug_len, x + lug_len, lug_width * 0.18, half_w[i] * 0.78, z_bot, z_top))
        else:
            lug_width = half_w[i] * (0.82 if i % 2 else 0.68)
            lugs.append(_box_mesh(x - lug_len, x + lug_len, -lug_width, lug_width, z_bot, z_top))
    return merge(*lugs)


def _texture_pattern(u: np.ndarray, y: np.ndarray, z: np.ndarray, design: dict) -> np.ndarray:
    preset = design.get("texture_preset", "woven_micro_rib")
    fu = float(design.get("texture_frequency_u", 34.0))
    fy = float(design.get("texture_frequency_y", 110.0))
    y_abs = np.abs(y)
    knit = 0.5 + 0.5 * np.sin(u * np.pi * (fu * 1.3) + y_abs * fy)
    cross = np.sin(u * np.pi * fu) * np.sin(y_abs * fy * 1.18)

    if preset == "pinky_relief_lattice":
        lateral = np.clip((-y - 0.010) / 0.045, 0, 1)
        forefoot = np.clip((u - 0.60) / 0.24, 0, 1) * np.clip((0.98 - u) / 0.20, 0, 1)
        diamond = np.maximum(cross, 0.0)
        pattern = 0.18 * knit + diamond * (0.55 + 0.78 * lateral * forefoot)
    elif preset == "medial_flow_ribs":
        medial = np.clip((y - 0.006) / 0.050, 0, 1)
        flow = 0.5 + 0.5 * np.sin(u * np.pi * fu + y * fy * 0.72 + z * 55)
        ribs = np.maximum(flow - 0.50, 0.0) * 2.0
        pattern = 0.20 * knit + ribs * (0.48 + 0.72 * medial)
    elif preset == "wave_lattice":
        wave = 0.5 + 0.5 * np.sin(u * np.pi * fu + y * fy * 0.42)
        lattice = np.maximum(np.sin(u * np.pi * (fu * 0.72)) * np.sin(y_abs * fy), 0)
        pattern = wave * 0.55 + lattice * 0.55
    elif preset == "soft_grid_relief":
        grid = np.maximum(np.sin(u * np.pi * fu), 0) * np.maximum(np.sin(y_abs * fy * 0.92), 0)
        toe = np.clip((u - 0.52) / 0.34, 0, 1)
        pattern = 0.22 * knit + grid * (0.55 + 0.35 * toe)
    else:
        fine = 0.5 + 0.5 * np.sin(u * np.pi * fu + y_abs * fy * 1.45)
        pattern = fine * 0.48 + np.maximum(cross, 0) * 0.32

    # 발등 통기/연성 구간은 미세하게 들어가고, 구조 리브는 올라오게 signed displacement.
    vent = np.maximum(np.sin(u * np.pi * (fu * 0.46) + y_abs * fy * 0.55), 0.0)
    vent_mask = np.clip((u - 0.28) / 0.20, 0, 1) * np.clip((0.76 - u) / 0.20, 0, 1) * (z > 0.028)
    return np.clip(pattern - vent * vent_mask * 0.28, -0.22, 1.28)


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
    y = out[:, 1]
    z = out[:, 2]
    pattern = _texture_pattern(u, y, z, design)

    toe_fade = np.clip((0.99 - u) / 0.06, 0, 1)
    heel_fade = np.clip((u - 0.06) / 0.08, 0, 1)
    mask = (u > 0.06) & (u < 0.99) & (z > 0.010)
    fade = toe_fade * heel_fade
    out += normals * (depth * pattern * mask * fade)[:, None]
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

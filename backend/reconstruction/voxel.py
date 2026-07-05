"""Voxel reconstruction helpers."""
from __future__ import annotations

import numpy as np


_CUBE_FACES = np.asarray([
    [0, 1, 2], [0, 2, 3],
    [4, 6, 5], [4, 7, 6],
    [0, 4, 5], [0, 5, 1],
    [1, 5, 6], [1, 6, 2],
    [2, 6, 7], [2, 7, 3],
    [3, 7, 4], [3, 4, 0],
], dtype=np.int32)

_CORNERS = np.asarray([
    [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
    [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1],
], dtype=np.float32)


def voxelize(points: np.ndarray, resolution: int = 32, max_voxels: int = 900) -> tuple[np.ndarray, np.ndarray, dict]:
    resolution = int(np.clip(resolution, 16, 56))
    if len(points) == 0:
        return np.zeros((0, 3), dtype=np.float32), np.zeros((0, 3), dtype=np.int32), {
            "resolution": resolution,
            "occupied": 0,
            "voxel_size_mm": 0.0,
            "confidence": 0.0,
        }

    lo = points.min(axis=0)
    hi = points.max(axis=0)
    extent = hi - lo
    cell = float(max(extent.max() / resolution, 1e-5))
    pad = cell * 1.5
    lo = lo - pad

    ijk = np.floor((points - lo) / cell).astype(np.int32)
    uniq, counts = np.unique(ijk, axis=0, return_counts=True)
    if len(uniq) > max_voxels:
        order = np.argsort(counts)[-max_voxels:]
        uniq = uniq[order]
        counts = counts[order]

    verts = []
    faces = []
    for grid in uniq:
        base = len(verts)
        verts.extend((lo + (grid + _CORNERS) * cell).tolist())
        faces.extend((_CUBE_FACES + base).tolist())

    confidence = min(0.94, 0.35 + len(uniq) / max(max_voxels, 1) * 0.45 + min(0.14, len(points) / 120000))
    report = {
        "resolution": resolution,
        "occupied": int(len(uniq)),
        "source_points": int(len(points)),
        "voxel_size_mm": round(cell * 1000.0, 2),
        "bounds_mm": [round(float(v), 1) for v in ((hi - (lo + pad)) * 1000.0)],
        "confidence": round(confidence, 2),
        "note": "포인트클라우드를 점유 voxel surface mesh로 변환한 제작/분석용 근사 결과",
    }
    return np.asarray(verts, dtype=np.float32), np.asarray(faces, dtype=np.int32), report

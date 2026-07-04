"""공용 메쉬 유틸리티: 단면 로프트, 법선, 오프셋, 병합."""
from __future__ import annotations

import numpy as np


def loft(sections: list[np.ndarray], cap_start: bool = True, cap_end: bool = True):
    """단면(각각 (M,3) 배열, 같은 M, 닫힌 폐곡선으로 취급)을 이어붙여 메쉬 생성.

    Returns (vertices (N,3) float32, faces (F,3) int32)
    """
    n_sec = len(sections)
    m = sections[0].shape[0]
    verts = np.concatenate(sections, axis=0).astype(np.float32)
    faces = []
    for i in range(n_sec - 1):
        a = i * m
        b = (i + 1) * m
        for j in range(m):
            j2 = (j + 1) % m
            faces.append([a + j, b + j, b + j2])
            faces.append([a + j, b + j2, a + j2])
    vlist = [verts]
    nv = verts.shape[0]
    if cap_start:
        c = sections[0].mean(axis=0, keepdims=True).astype(np.float32)
        vlist.append(c)
        ci = nv
        nv += 1
        for j in range(m):
            faces.append([ci, (j + 1) % m, j])
    if cap_end:
        c = sections[-1].mean(axis=0, keepdims=True).astype(np.float32)
        vlist.append(c)
        ci = nv
        base = (n_sec - 1) * m
        for j in range(m):
            faces.append([ci, base + j, base + (j + 1) % m])
    verts = np.concatenate(vlist, axis=0)
    return verts, np.asarray(faces, dtype=np.int32)


def vertex_normals(verts: np.ndarray, faces: np.ndarray) -> np.ndarray:
    vn = np.zeros_like(verts, dtype=np.float64)
    tri = verts[faces]
    fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    for k in range(3):
        np.add.at(vn, faces[:, k], fn)
    norm = np.linalg.norm(vn, axis=1, keepdims=True)
    norm[norm < 1e-12] = 1.0
    return (vn / norm).astype(np.float32)


def offset_mesh(verts: np.ndarray, faces: np.ndarray, dist: float):
    """법선 방향으로 균일 오프셋(간이 shell)."""
    return (verts + vertex_normals(verts, faces) * dist).astype(np.float32), faces


def merge(*meshes):
    vs, fs, off = [], [], 0
    for v, f in meshes:
        vs.append(v)
        fs.append(f + off)
        off += v.shape[0]
    return np.concatenate(vs).astype(np.float32), np.concatenate(fs).astype(np.int32)


def smooth_profile(xs: np.ndarray, knots_x, knots_y) -> np.ndarray:
    """단조 x 노트에 대한 부드러운(코사인 보간) 프로파일."""
    kx = np.asarray(knots_x, dtype=np.float64)
    ky = np.asarray(knots_y, dtype=np.float64)
    ys = np.empty_like(xs, dtype=np.float64)
    for i, x in enumerate(xs):
        if x <= kx[0]:
            ys[i] = ky[0]
        elif x >= kx[-1]:
            ys[i] = ky[-1]
        else:
            k = np.searchsorted(kx, x) - 1
            t = (x - kx[k]) / (kx[k + 1] - kx[k])
            t = 0.5 - 0.5 * np.cos(np.pi * t)
            ys[i] = ky[k] * (1 - t) + ky[k + 1] * t
    return ys

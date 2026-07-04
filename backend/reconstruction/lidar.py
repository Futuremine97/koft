"""LiDAR 포인트클라우드 파싱 및 사진 재구성과의 융합.

지원 포맷:
- .ply (ascii / binary_little_endian, x y z [기타 속성])
- .json ({"points": [[x,y,z], ...]}) — iOS ARKit 내보내기 등
- .xyz / .txt (공백 구분 x y z)

LiDAR는 미터 단위 절대 스케일을 제공하므로, 융합 시 사진 기반
포인트클라우드의 스케일을 LiDAR 발 길이에 맞춰 보정한다.
"""
from __future__ import annotations

import json
import struct

import numpy as np


def parse(filename: str, data: bytes) -> np.ndarray:
    name = filename.lower()
    if name.endswith(".ply"):
        return _parse_ply(data)
    if name.endswith(".json"):
        obj = json.loads(data.decode("utf-8"))
        pts = obj["points"] if isinstance(obj, dict) else obj
        return np.asarray(pts, dtype=np.float32)[:, :3]
    # xyz / txt
    rows = []
    for line in data.decode("utf-8", errors="ignore").splitlines():
        parts = line.replace(",", " ").split()
        if len(parts) >= 3:
            try:
                rows.append([float(parts[0]), float(parts[1]), float(parts[2])])
            except ValueError:
                continue
    if not rows:
        raise ValueError("LiDAR 파일에서 포인트를 읽지 못했습니다.")
    return np.asarray(rows, dtype=np.float32)


def _parse_ply(data: bytes) -> np.ndarray:
    header_end = data.find(b"end_header\n")
    if header_end < 0:
        raise ValueError("PLY 헤더가 올바르지 않습니다.")
    header = data[:header_end].decode("ascii", errors="ignore")
    body = data[header_end + len(b"end_header\n"):]

    fmt = "ascii"
    n_verts = 0
    props: list[tuple[str, str]] = []
    in_vertex = False
    for line in header.splitlines():
        t = line.strip().split()
        if not t:
            continue
        if t[0] == "format":
            fmt = t[1]
        elif t[0] == "element":
            in_vertex = t[1] == "vertex"
            if in_vertex:
                n_verts = int(t[2])
        elif t[0] == "property" and in_vertex and t[1] != "list":
            props.append((t[2], t[1]))

    names = [p[0] for p in props]
    ix, iy, iz = names.index("x"), names.index("y"), names.index("z")

    if fmt == "ascii":
        vals = []
        for line in body.decode("ascii", errors="ignore").splitlines()[:n_verts]:
            parts = line.split()
            if len(parts) >= len(props):
                vals.append([float(parts[ix]), float(parts[iy]), float(parts[iz])])
        return np.asarray(vals, dtype=np.float32)

    type_size = {"float": 4, "float32": 4, "double": 8, "float64": 8,
                 "int": 4, "int32": 4, "uint": 4, "uint32": 4,
                 "short": 2, "ushort": 2, "int16": 2, "uint16": 2,
                 "char": 1, "uchar": 1, "int8": 1, "uint8": 1}
    type_fmt = {"float": "f", "float32": "f", "double": "d", "float64": "d",
                "int": "i", "int32": "i", "uint": "I", "uint32": "I",
                "short": "h", "ushort": "H", "int16": "h", "uint16": "H",
                "char": "b", "uchar": "B", "int8": "b", "uint8": "B"}
    endian = "<" if "little" in fmt else ">"
    stride = sum(type_size[t] for _, t in props)
    offsets = {}
    off = 0
    for n, t in props:
        offsets[n] = (off, type_fmt[t])
        off += type_size[t]

    pts = np.empty((n_verts, 3), dtype=np.float32)
    for i in range(n_verts):
        base = i * stride
        for j, key in enumerate(("x", "y", "z")):
            o, f = offsets[key]
            pts[i, j] = struct.unpack_from(endian + f, body, base + o)[0]
    return pts


def clean(points: np.ndarray) -> np.ndarray:
    """이상치 제거: 발끝/뒤꿈치 끝점은 보존하고 진짜 아웃라이어만 제거."""
    center = np.median(points, axis=0)
    d = np.linalg.norm(points - center, axis=1)
    return points[d < 1.25 * np.quantile(d, 0.95)]


def fuse(photo_pts: np.ndarray, lidar_pts: np.ndarray) -> tuple[np.ndarray, float]:
    """사진 포인트클라우드를 LiDAR 절대 스케일에 맞춰 보정 후 병합.

    Returns (융합 포인트클라우드, 적용된 스케일 팩터)
    """
    lidar_pts = clean(lidar_pts)

    def main_extent(p):
        c = p - p.mean(axis=0)
        cov = np.cov(c.T)
        w, v = np.linalg.eigh(cov)
        axis = v[:, -1]
        proj = c @ axis
        return float(np.quantile(proj, 0.99) - np.quantile(proj, 0.01))

    scale = 1.0
    ext_photo = main_extent(photo_pts)
    ext_lidar = main_extent(lidar_pts)
    if ext_photo > 1e-9:
        scale = ext_lidar / ext_photo
    photo_scaled = (photo_pts - photo_pts.mean(axis=0)) * scale + lidar_pts.mean(axis=0)
    fused = np.concatenate([photo_scaled, lidar_pts]).astype(np.float32)
    if len(fused) > 80000:
        idx = np.random.default_rng(0).choice(len(fused), 80000, replace=False)
        fused = fused[idx]
    return fused, scale

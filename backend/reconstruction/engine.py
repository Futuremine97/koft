"""재구성 오케스트레이터: 엔진 선택 → LiDAR 융합 → 정렬/스케일 보정."""
from __future__ import annotations

from typing import Optional

import numpy as np

from . import api_engine, demo_engine, lidar, nerf_engine, vggt_engine


def align_foot(points: np.ndarray) -> np.ndarray:
    """PCA 정렬: 주축→x(길이), 바닥→z=0, 뒤꿈치→x=0, 위→+z."""
    c = points.mean(axis=0)
    p = points - c
    cov = np.cov(p.T)
    w, v = np.linalg.eigh(cov)
    # 고유값 내림차순: 주축(길이), 부축(폭), 최소축(높이 아님 — 발은 폭>높이인 경우가 많아
    # 길이축만 확정하고 나머지는 z-분산 기준으로 결정)
    axes = v[:, ::-1].T  # rows: 주축, 2nd, 3rd
    R = np.eye(3)
    R[0] = axes[0]
    # 남은 두 축 중 분산 작은 쪽을 z로
    R[2] = axes[2]
    R[1] = np.cross(R[2], R[0])
    p = np.einsum("ij,kj->ki", R, p)

    # 바닥을 z=0으로
    p[:, 2] -= np.quantile(p[:, 2], 0.02)
    # 상하반전 검사: 발은 바닥(하단)이 상단보다 넓다
    z_top = np.quantile(p[:, 2], 0.98)
    if z_top > 1e-9:
        low = p[p[:, 2] < 0.3 * z_top]
        high = p[p[:, 2] > 0.7 * z_top]
        def _w(q):
            return (np.quantile(q[:, 1], 0.98) - np.quantile(q[:, 1], 0.02)
                    if len(q) > 20 else 0.0)
        if _w(high) > _w(low):  # 위가 더 넓으면 뒤집힌 상태
            p[:, 2] = z_top - p[:, 2]
            p[:, 1] = -p[:, 1]  # 오른손 좌표계 유지
            p[:, 2] -= np.quantile(p[:, 2], 0.02)
    # 뒤꿈치를 x=0으로
    p[:, 0] -= np.quantile(p[:, 0], 0.005)
    # 발끝이 +x가 되도록: 발끝쪽이 낮고 좁다 → 높이 무게중심이 앞쪽보다 뒤쪽에 있음
    n = len(p)
    L = np.quantile(p[:, 0], 0.995)
    front_h = np.quantile(p[p[:, 0] > 0.7 * L, 2], 0.95) if n else 0
    back_h = np.quantile(p[p[:, 0] < 0.3 * L, 2], 0.95) if n else 0
    if front_h > back_h:  # 앞이 더 높으면 방향 반대
        p[:, 0] = L - p[:, 0]
        p[:, 1] = -p[:, 1]
    p[:, 1] -= np.median(p[:, 1])
    return p.astype(np.float32)


def reconstruct(
    image_bytes: list[bytes],
    engine: str = "auto",
    lidar_file: Optional[tuple[str, bytes]] = None,
    use_lidar: bool = False,
    true_length_mm: Optional[float] = None,
    api_model: Optional[str] = None,
) -> dict:
    requested = engine
    api_model = (api_model or "").strip() or "custom"
    if engine == "auto":
        engine = "vggt" if vggt_engine.available() else "demo"

    if engine == "vggt":
        try:
            result = vggt_engine.reconstruct(image_bytes)
        except vggt_engine.EngineUnavailable as e:
            if requested == "vggt":
                raise
            result = demo_engine.reconstruct(image_bytes, true_length_mm)
            result["note"] += f" (VGGT 폴백 사유: {e})"
    elif engine == "nerf":
        nerf_api = next((m["id"] for m in api_engine.available_models() if m.get("kind") == "nerf"), "")
        if nerf_api:
            try:
                result = api_engine.reconstruct(image_bytes, nerf_api, true_length_mm=true_length_mm)
            except api_engine.APIEngineUnavailable as e:
                result = nerf_engine.reconstruct(image_bytes, true_length_mm=true_length_mm)
                result["note"] += f" (NeRF API 폴백 사유: {e})"
        else:
            result = nerf_engine.reconstruct(image_bytes, true_length_mm=true_length_mm)
    elif engine == "api" or engine.startswith("api:"):
        model_id = engine.split(":", 1)[1] if engine.startswith("api:") else api_model
        result = api_engine.reconstruct(image_bytes, model_id, true_length_mm=true_length_mm)
    elif engine == "voxel":
        result = demo_engine.reconstruct(image_bytes, true_length_mm)
        result["engine"] = "voxel"
        result["note"] += " Voxel 모드: 후처리 단계에서 점유 voxel mesh를 함께 생성."
    else:
        result = demo_engine.reconstruct(image_bytes, true_length_mm)

    pts = result["points"]
    fused_scale = None

    if use_lidar and lidar_file is not None:
        lpts = lidar.parse(*lidar_file)
        pts, fused_scale = lidar.fuse(pts, lpts)
        result["mesh"] = None  # 융합 후 메쉬는 무효 → 후단에서 재생성

    pts = align_foot(pts)

    # 스케일 보정: LiDAR(절대) > 실측 길이 > 엔진 자체 스케일
    cur_len = float(np.quantile(pts[:, 0], 0.995) - np.quantile(pts[:, 0], 0.005))
    scale_source = "engine"
    if use_lidar and fused_scale is not None:
        scale_source = "lidar"
    elif true_length_mm and cur_len > 1e-6:
        s = (true_length_mm / 1000.0) / cur_len
        pts *= s
        scale_source = "user_length"
    elif result["engine"] == "vggt" and not (0.15 < cur_len < 0.40):
        # VGGT 상대 스케일 → 평균 발 길이로 가정 정규화
        s = 0.255 / max(cur_len, 1e-6)
        pts *= s
        scale_source = "assumed_avg(255mm)"

    result["points"] = pts
    result["scale_source"] = scale_source
    result["lidar_used"] = bool(use_lidar and lidar_file is not None)
    return result


def status() -> dict:
    external = api_engine.available_models()
    engines = [
        {"id": "auto", "label": "자동", "available": True, "kind": "router"},
        {"id": "demo", "label": "데모 통계 모델", "available": True, "kind": "local"},
        {"id": "voxel", "label": "Voxel reconstruction", "available": True, "kind": "local"},
        {"id": "nerf", "label": "NeRF/API volumetric", "available": True, "kind": "local_or_api"},
        {"id": "vggt", "label": "VGGT", "available": vggt_engine.available(), "kind": "local"},
    ]
    engines.extend({
        "id": f"api:{m['id']}",
        "label": f"API: {m['id']}",
        "available": m.get("configured", False),
        "kind": m.get("kind", "api"),
        "has_key": m.get("has_key", False),
    } for m in external)
    return {
        "vggt_available": vggt_engine.available(),
        "active_default": "vggt" if vggt_engine.available() else "demo",
        "engines": engines,
        "external_models": external,
    }

"""NeRF/volumetric reconstruction adapter.

실제 NeRF 학습/추론은 GPU와 장면별 최적화 또는 외부 API가 필요하다. 이 모듈은
외부 NeRF API가 없을 때 앱 파이프라인을 유지하기 위한 로컬 volumetric proxy를
제공한다.
"""
from __future__ import annotations

import numpy as np

from . import demo_engine


def reconstruct(image_bytes: list[bytes], true_length_mm: float | None = None) -> dict:
    base = demo_engine.reconstruct(image_bytes, true_length_mm=true_length_mm, n_points=26000)
    pts = base["points"]

    # NeRF식 연속 radiance/occupancy field의 샘플링을 흉내 내는 얇은 볼륨 샘플.
    rng = np.random.default_rng(42)
    jitter = rng.normal(0.0, 0.0012, pts.shape).astype(np.float32)
    field_pts = np.concatenate([pts, pts + jitter], axis=0)

    base["engine"] = "nerf"
    base["points"] = field_pts
    base["note"] = (
        "NeRF 모드: 외부 NeRF API가 없어서 로컬 volumetric proxy로 재구성했습니다. "
        "실제 NeRF/3DGS 품질은 KOFT_AI_MODELS_JSON에 NeRF API를 연결해 사용하세요."
    )
    base["field"] = {
        "type": "nerf_proxy",
        "samples": int(len(field_pts)),
        "density_basis": "demo_surface_with_local_volume_jitter",
    }
    return base

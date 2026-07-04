"""VGGT (Visual Geometry Grounded Transformer, CVPR 2025) 실제 추론 엔진.

사진 몇 장 → feed-forward 한 번의 추론으로 카메라 포즈 + dense point map을
동시에 추정한다. NeRF/3DGS처럼 장면별 학습이 필요 없어 희소 뷰(3~10장)에
훨씬 적합한 현 SoTA 계열.

설치:
    pip install torch torchvision
    pip install git+https://github.com/facebookresearch/vggt.git
최초 실행 시 HuggingFace에서 가중치(~5GB, facebook/VGGT-1B) 자동 다운로드.
"""
from __future__ import annotations

import io
import tempfile
from pathlib import Path

import numpy as np


class EngineUnavailable(RuntimeError):
    pass


def available() -> bool:
    try:
        import torch  # noqa: F401
        import vggt  # noqa: F401
        return True
    except Exception:
        return False


_model = None


def _load_model():
    global _model
    if _model is not None:
        return _model
    import torch
    from vggt.models.vggt import VGGT

    device = "cuda" if torch.cuda.is_available() else "cpu"
    _model = VGGT.from_pretrained("facebook/VGGT-1B").to(device).eval()
    _model._device = device
    return _model


def _segment_foot(points: np.ndarray, conf: np.ndarray) -> np.ndarray:
    """신뢰도 필터 + 중앙 물체(발) 분리: 배경 제거 휴리스틱."""
    mask = conf > np.quantile(conf, 0.6)
    pts = points[mask]
    if len(pts) < 1000:
        pts = points[conf > np.quantile(conf, 0.3)]
    # 중앙값 기준 반경 클리핑으로 배경/바닥 제거
    center = np.median(pts, axis=0)
    d = np.linalg.norm(pts - center, axis=1)
    pts = pts[d < np.quantile(d, 0.85)]
    return pts.astype(np.float32)


def reconstruct(image_bytes: list[bytes], **_) -> dict:
    if not available():
        raise EngineUnavailable(
            "torch/vggt 미설치. requirements.txt 주석 참고 후 설치하세요."
        )
    import torch
    from vggt.utils.load_fn import load_and_preprocess_images
    from vggt.utils.pose_enc import pose_encoding_to_extri_intri
    from vggt.utils.geometry import unproject_depth_map_to_point_map

    model = _load_model()
    device = model._device
    dtype = (
        torch.bfloat16
        if device == "cuda" and torch.cuda.get_device_capability()[0] >= 8
        else torch.float32
    )

    with tempfile.TemporaryDirectory() as td:
        paths = []
        for i, b in enumerate(image_bytes):
            p = Path(td) / f"img_{i:02d}.png"
            from PIL import Image

            Image.open(io.BytesIO(b)).convert("RGB").save(p)
            paths.append(str(p))
        images = load_and_preprocess_images(paths).to(device)

    with torch.no_grad():
        with torch.autocast(device_type=device.split(":")[0], dtype=dtype,
                            enabled=device != "cpu"):
            preds = model(images)

    extrinsic, intrinsic = pose_encoding_to_extri_intri(
        preds["pose_enc"], images.shape[-2:]
    )
    depth = preds["depth"].squeeze(0).cpu().numpy()
    depth_conf = preds["depth_conf"].squeeze(0).cpu().numpy()
    point_map = unproject_depth_map_to_point_map(
        depth, extrinsic.squeeze(0).cpu().numpy(), intrinsic.squeeze(0).cpu().numpy()
    )

    pts = point_map.reshape(-1, 3)
    conf = depth_conf.reshape(-1)
    pts = _segment_foot(pts, conf)

    # 다운샘플
    if len(pts) > 60000:
        idx = np.random.default_rng(0).choice(len(pts), 60000, replace=False)
        pts = pts[idx]

    return {
        "engine": "vggt",
        "points": pts,
        "mesh": None,  # 메쉬는 파이프라인 후단에서 측정치 기반으로 재구성
        "params": None,
        "note": "VGGT-1B feed-forward 추론 결과. 스케일은 상대적이므로 "
                "LiDAR 또는 실측 길이로 미터 보정 필요.",
    }

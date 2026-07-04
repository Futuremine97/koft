"""데모 재구성 엔진.

실제 SoTA 모델(VGGT)이 설치되어 있지 않을 때 사용하는 폴백.
업로드된 사진에서 결정적(deterministic) 시드를 뽑아 통계적 발 형상 모델
(파라메트릭)을 개인화한 뒤, 표면 포인트클라우드 + 메쉬를 생성한다.

- 스케일: 사용자가 실측 발 길이(mm)를 입력하면 그 값 사용,
  아니면 사진 기반 시드로 성인 평균 범위(235~285mm)에서 결정.
- 인터페이스는 vggt_engine 과 동일: reconstruct(images, ...) -> dict
"""
from __future__ import annotations

import hashlib
import io
from typing import Optional

import numpy as np
from PIL import Image

from ..meshutil import loft, smooth_profile


def _seed_from_images(image_bytes: list[bytes]) -> np.random.Generator:
    h = hashlib.sha256()
    for b in image_bytes:
        h.update(b[:65536])
    return np.random.default_rng(int.from_bytes(h.digest()[:8], "little"))


def _image_cue(image_bytes: list[bytes]) -> float:
    """사진의 평균 종횡비로 발 폭 경향을 아주 약하게 반영 (데모용 개인화 신호)."""
    ratios = []
    for b in image_bytes[:4]:
        try:
            im = Image.open(io.BytesIO(b))
            ratios.append(im.width / max(im.height, 1))
        except Exception:
            pass
    if not ratios:
        return 0.0
    return float(np.clip((np.mean(ratios) - 1.0) * 0.05, -0.03, 0.03))


def foot_sections(params: dict, n_sec: int = 60, n_around: int = 48):
    """파라메트릭 발 형상: x=0(뒤꿈치)→x=L(발끝) 단면 로프트."""
    L = params["length"]
    bw = params["ball_width"]
    hw = params["heel_width"]
    ih = params["instep_height"]
    ah = params["arch_height"]
    th = params["toe_height"]

    xs = np.linspace(0.0, L, n_sec)
    # 폭 프로파일 (반폭)
    half_w = smooth_profile(
        xs / L,
        [0.0, 0.05, 0.16, 0.45, 0.62, 0.72, 0.88, 0.97, 1.0],
        [0.15 * hw, 0.42 * hw, 0.5 * hw, 0.44 * bw, 0.485 * bw, 0.5 * bw,
         0.46 * bw, 0.30 * bw, 0.06 * bw],
    )
    # 높이 프로파일 (등/발등)
    top_h = smooth_profile(
        xs / L,
        [0.0, 0.06, 0.2, 0.42, 0.55, 0.72, 0.9, 1.0],
        [0.55 * ih, 0.92 * ih, 0.98 * ih, 1.0 * ih, 0.9 * ih, 0.55 * ih,
         1.15 * th, 0.5 * th],
    )
    # 아치(내측 중족부 바닥 융기) 세기
    arch_amp = smooth_profile(
        xs / L, [0.0, 0.25, 0.42, 0.55, 0.7, 1.0], [0, 0.15, 1.0, 0.9, 0.1, 0]
    ) * ah

    # 단면: 비대칭 프로파일 — 바닥은 평평하고 넓게(발바닥), 위는 둥글게(발등)
    t = np.linspace(0, 2 * np.pi, n_around, endpoint=False)
    cy = np.sign(np.cos(t)) * np.abs(np.cos(t)) ** (2 / 3)
    sin_t = np.sin(t)
    z_unit = np.where(
        sin_t >= 0,
        0.5 * (1 + np.abs(sin_t) ** (2 / 3)),   # 윗면: 둥근 발등
        0.5 * (1 - np.abs(sin_t) ** 0.25),      # 바닥: 평평하고 넓음
    )
    sections = []
    for i, x in enumerate(xs):
        y = half_w[i] * cy
        z = top_h[i] * z_unit
        # 내측(y>0) 아치 융기: 바닥면만 들어올림
        medial = np.clip(y / max(half_w[i], 1e-9), 0, 1) ** 1.5
        floor = arch_amp[i] * medial
        z = np.maximum(z, floor)
        sec = np.stack([np.full_like(y, x), y, z], axis=1)
        sections.append(sec.astype(np.float32))
    return sections


def sample_surface(verts: np.ndarray, faces: np.ndarray, n: int, rng) -> np.ndarray:
    tri = verts[faces]
    areas = 0.5 * np.linalg.norm(
        np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1
    )
    probs = areas / areas.sum()
    idx = rng.choice(len(faces), size=n, p=probs)
    u = rng.random(n)
    v = rng.random(n)
    flip = u + v > 1
    u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
    p = (
        tri[idx, 0]
        + u[:, None] * (tri[idx, 1] - tri[idx, 0])
        + v[:, None] * (tri[idx, 2] - tri[idx, 0])
    )
    return p.astype(np.float32)


def reconstruct(
    image_bytes: list[bytes],
    true_length_mm: Optional[float] = None,
    n_points: int = 20000,
) -> dict:
    rng = _seed_from_images(image_bytes)
    cue = _image_cue(image_bytes)

    L = (true_length_mm / 1000.0) if true_length_mm else float(
        rng.uniform(0.235, 0.285)
    )
    wr = float(np.clip(rng.normal(0.395, 0.018) + cue, 0.35, 0.45))  # 폭/길이비
    params = {
        "length": L,
        "ball_width": wr * L,
        "heel_width": wr * L * float(rng.uniform(0.70, 0.78)),
        "instep_height": L * float(rng.uniform(0.255, 0.30)),
        "arch_height": L * float(rng.uniform(0.04, 0.10)),
        "toe_height": L * float(rng.uniform(0.075, 0.095)),
    }
    sections = foot_sections(params)
    verts, faces = loft(sections)
    pts = sample_surface(verts, faces, n_points, rng)
    # 스캔 노이즈 시뮬레이션
    pts += rng.normal(0, 0.0006, pts.shape).astype(np.float32)

    return {
        "engine": "demo",
        "points": pts,               # (N,3) meters, x=길이축, z=위
        "mesh": (verts, faces),      # 워터타이트 근사 메쉬
        "params": params,
        "note": "데모 엔진: 사진 기반 시드로 개인화된 통계적 발 모델. "
                "실측 정확도가 필요하면 VGGT 설치 또는 LiDAR 사용.",
    }

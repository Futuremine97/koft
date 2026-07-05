"""외부 3D/NeRF 재구성 API 어댑터.

환경변수 `KOFT_AI_MODELS_JSON` 예:
{
  "nerf_cloud": {
    "url": "https://example.com/reconstruct",
    "api_key_env": "NERF_API_KEY",
    "kind": "nerf"
  }
}

응답 JSON은 최소 `{ "points": [[x,y,z], ...] }` 형식을 기대한다.
선택적으로 `{ "mesh": { "vertices": [...], "faces": [...] } }`도 받을 수 있다.
"""
from __future__ import annotations

import json
import os
import uuid
from urllib import request

import numpy as np


class APIEngineUnavailable(RuntimeError):
    pass


def _load_models() -> dict:
    raw = os.getenv("KOFT_AI_MODELS_JSON", "").strip()
    models = {}
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                models.update(parsed)
        except json.JSONDecodeError as e:
            raise APIEngineUnavailable(f"KOFT_AI_MODELS_JSON 파싱 실패: {e}") from e

    url = os.getenv("KOFT_RECON_API_URL", "").strip()
    if url:
        models.setdefault("custom", {
            "url": url,
            "api_key_env": "KOFT_RECON_API_KEY",
            "kind": os.getenv("KOFT_RECON_API_KIND", "reconstruction"),
        })
    return models


def available_models() -> list[dict]:
    items = []
    for model_id, cfg in _load_models().items():
        key_env = cfg.get("api_key_env", "")
        items.append({
            "id": model_id,
            "kind": cfg.get("kind", "reconstruction"),
            "configured": bool(cfg.get("url")),
            "has_key": bool(os.getenv(key_env)) if key_env else True,
        })
    return items


def _multipart(images: list[bytes], model_id: str, true_length_mm: float | None) -> tuple[bytes, str]:
    boundary = f"----koft-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    def add_field(name: str, value: str):
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            value.encode(),
            b"\r\n",
        ])

    add_field("model", model_id)
    if true_length_mm:
        add_field("true_length_mm", str(true_length_mm))

    for i, data in enumerate(images):
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="photos"; filename="photo_{i}.jpg"\r\n'.encode(),
            b"Content-Type: image/jpeg\r\n\r\n",
            data,
            b"\r\n",
        ])

    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def reconstruct(
    image_bytes: list[bytes],
    model_id: str = "custom",
    true_length_mm: float | None = None,
) -> dict:
    models = _load_models()
    cfg = models.get(model_id)
    if not cfg:
        raise APIEngineUnavailable(f"API 모델 '{model_id}' 설정이 없습니다.")

    url = cfg.get("url")
    if not url:
        raise APIEngineUnavailable(f"API 모델 '{model_id}' URL이 비어 있습니다.")

    body, content_type = _multipart(image_bytes, model_id, true_length_mm)
    headers = {
        "Content-Type": content_type,
        "Accept": "application/json",
    }
    key_env = cfg.get("api_key_env")
    if key_env and os.getenv(key_env):
        headers["Authorization"] = f"Bearer {os.getenv(key_env)}"

    timeout = float(cfg.get("timeout_sec", os.getenv("KOFT_RECON_API_TIMEOUT", "120")))
    req = request.Request(url, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as res:
            payload = json.loads(res.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        raise APIEngineUnavailable(f"API 모델 '{model_id}' 호출 실패: {e}") from e

    points = np.asarray(payload.get("points", []), dtype=np.float32)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) < 128:
        raise APIEngineUnavailable("API 응답에 유효한 points 배열이 없습니다.")

    mesh = None
    mesh_payload = payload.get("mesh")
    if isinstance(mesh_payload, dict):
        verts = np.asarray(mesh_payload.get("vertices", []), dtype=np.float32)
        faces = np.asarray(mesh_payload.get("faces", []), dtype=np.int32)
        if verts.ndim == 2 and verts.shape[1] == 3 and faces.ndim == 2 and faces.shape[1] == 3:
            mesh = (verts, faces)

    return {
        "engine": f"api:{model_id}",
        "points": points,
        "mesh": mesh,
        "params": payload.get("params", {}),
        "note": payload.get("note", f"외부 AI API 모델 '{model_id}' 결과 사용"),
        "api_model": {
            "id": model_id,
            "kind": cfg.get("kind", "reconstruction"),
            "url_configured": True,
        },
    }

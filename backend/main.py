"""FootFit AI — 사진 몇 장으로 발 3D 재구성 + 신발 inverse design.

실행:  uvicorn backend.main:app --reload --port 8000
접속:  http://localhost:8000
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .analysis.dynamics import simulate_dynamic_comfort
from .analysis.fit import assess_fit
from .analysis.measurements import measure
from .analysis.sizing import recommend
from .design.export import points_to_ply, to_obj, to_stl
from .design.insole import build_insole
from .design.last import build_last
from .design.quality import assess_artifact_quality
from .design.recommendation import recommend_design
from .design.shoe import build_shoe
from .design.toes import reconstruct_toes
from .meshutil import loft
from .reconstruction import engine as recon_engine
from .reconstruction.demo_engine import foot_sections

app = FastAPI(title="FootFit AI")

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
VIEW_POINT_LIMIT = int(os.getenv("VIEW_POINT_LIMIT", "6000" if os.getenv("VERCEL") else "15000"))
LICENSE_NOTICE = {
    "product": "Koft / FootFit AI",
    "copyright": "Copyright (c) 2026 Futuremine97 (Koft). All rights reserved.",
    "license": "Proprietary - All Rights Reserved",
    "usage": "No copying, redistribution, hosting, commercialization, or derivative works without written permission.",
}

# 세션 결과 저장 (메모리, localhost 용)
RESULTS: dict[str, dict] = {}


@app.middleware("http")
async def add_license_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Koft-License"] = "Proprietary; all rights reserved"
    response.headers["X-Koft-Copyright"] = "Copyright 2026 Futuremine97 (Koft)"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _mesh_json(verts: np.ndarray, faces: np.ndarray) -> dict:
    return {
        "vertices": np.round(verts, 5).flatten().tolist(),
        "faces": faces.flatten().tolist(),
    }


def _foot_mesh_from_measurements(meas: dict):
    """VGGT/LiDAR 결과처럼 메쉬가 없을 때 측정치로 표시용 발 메쉬 생성."""
    p = {
        "length": meas["foot_length_mm"] / 1000,
        "ball_width": meas["ball_width_mm"] / 1000,
        "heel_width": meas["heel_width_mm"] / 1000,
        "instep_height": meas["instep_height_mm"] / 1000,
        "arch_height": meas["arch_height_mm"] / 1000,
        "toe_height": meas["foot_length_mm"] / 1000 * 0.085,
    }
    return loft(foot_sections(p))


@app.get("/api/status")
def status():
    return recon_engine.status()


@app.get("/api/license")
def license_info():
    return LICENSE_NOTICE


@app.post("/api/reconstruct")
async def reconstruct(
    photos: list[UploadFile] = File(...),
    lidar: Optional[UploadFile] = File(None),
    use_lidar: bool = Form(False),
    engine: str = Form("auto"),
    fit: str = Form("everyday"),
    true_length_mm: Optional[float] = Form(None),
):
    if len(photos) < 2:
        raise HTTPException(400, "사진을 최소 2장 업로드하세요 (권장 4~8장).")

    image_bytes = [await p.read() for p in photos]
    lidar_file = None
    if lidar is not None and lidar.filename:
        lidar_file = (lidar.filename, await lidar.read())

    try:
        result = recon_engine.reconstruct(
            image_bytes,
            engine=engine,
            lidar_file=lidar_file,
            use_lidar=use_lidar,
            true_length_mm=true_length_mm,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"재구성 실패: {e}") from e

    pts = result["points"]
    meas = measure(pts)
    sizing = recommend(meas, fit=fit)
    lp = sizing["last_params"]
    base_fit = assess_fit(meas, lp, fit=fit)
    design = recommend_design(meas, sizing, fit=fit, fit_assessment=base_fit)
    fit_assessment = assess_fit(meas, lp, fit=fit, design_profile=design["mesh_params"])
    design["fit_assessment"] = fit_assessment

    foot_mesh = result["mesh"] or _foot_mesh_from_measurements(meas)
    toes_mesh, toe_reconstruction = reconstruct_toes(pts, meas)
    dynamic_simulation = simulate_dynamic_comfort(
        meas,
        sizing,
        fit_assessment,
        design,
        fit=fit,
        toe_reconstruction=toe_reconstruction,
    )
    design["dynamic_simulation"] = dynamic_simulation
    artifact_quality = assess_artifact_quality(
        meas,
        sizing,
        fit_assessment,
        design,
        dynamic_simulation,
        toe_reconstruction,
        engine_used=result["engine"],
        lidar_used=result["lidar_used"],
    )
    design["artifact_quality"] = artifact_quality
    design["license"] = LICENSE_NOTICE
    last_mesh = build_last(lp)
    shoe_mesh = build_shoe(lp, design_profile=design["mesh_params"])
    insole_mesh = build_insole(meas, lp)

    rid = uuid.uuid4().hex[:12]
    RESULTS[rid] = {
        "points": pts,
        "foot": foot_mesh,
        "toes": toes_mesh,
        "last": last_mesh,
        "shoe": shoe_mesh,
        "insole": insole_mesh,
        "design": design,
    }
    if len(RESULTS) > 20:  # 메모리 관리
        RESULTS.pop(next(iter(RESULTS)))

    # 뷰어용 포인트 다운샘플
    view_pts = pts
    if len(view_pts) > VIEW_POINT_LIMIT:
        idx = np.random.default_rng(0).choice(len(view_pts), VIEW_POINT_LIMIT, replace=False)
        view_pts = view_pts[idx]

    return JSONResponse({
        "result_id": rid,
        "engine_used": result["engine"],
        "scale_source": result["scale_source"],
        "lidar_used": result["lidar_used"],
        "note": result.get("note", ""),
        "n_photos": len(image_bytes),
        "measurements": meas,
        "toe_reconstruction": toe_reconstruction,
        "dynamic_simulation": dynamic_simulation,
        "artifact_quality": artifact_quality,
        "sizing": sizing,
        "fit_assessment": fit_assessment,
        "design": design,
        "points": np.round(view_pts, 5).flatten().tolist(),
        "meshes": {
            "foot": _mesh_json(*foot_mesh),
            "toes": _mesh_json(*toes_mesh),
            "last": _mesh_json(*last_mesh),
            "shoe": _mesh_json(*shoe_mesh),
            "insole": _mesh_json(*insole_mesh),
        },
    })


@app.get("/api/export/{rid}/{kind}.{fmt}")
def export(rid: str, kind: str, fmt: str):
    if rid not in RESULTS:
        raise HTTPException(404, "결과가 만료되었습니다. 다시 재구성하세요.")
    store = RESULTS[rid]
    if kind == "points":
        if fmt != "ply":
            raise HTTPException(400, "포인트클라우드는 .ply만 지원")
        data = points_to_ply(store["points"])
        media = "application/octet-stream"
    elif kind == "design":
        if fmt != "json":
            raise HTTPException(400, "디자인 브리프는 .json만 지원")
        data = json.dumps(store["design"], ensure_ascii=False, indent=2).encode("utf-8")
        media = "application/json"
    elif kind in ("foot", "toes", "last", "shoe", "insole"):
        v, f = store[kind]
        if fmt == "stl":
            data = to_stl(v, f, name=f"Koft proprietary {kind}".encode())
        elif fmt == "obj":
            data = to_obj(v, f)
        else:
            raise HTTPException(400, "stl 또는 obj만 지원")
        media = "model/stl" if fmt == "stl" else "text/plain"
    else:
        raise HTTPException(404, "unknown kind")
    return Response(
        data,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{kind}.{fmt}"'},
    )


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

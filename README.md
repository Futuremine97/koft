# FootFit AI — 발 3D 재구성 & 신발 Inverse Design (localhost)

사진 몇 장(2~8장)으로 발을 3D 재구성하고, 측정치 기반으로 최적의
라스트(신발골)·신발·인솔을 역설계(inverse design)하는 로컬 웹앱.

## 빠른 시작

```bash
./run.sh          # 가상환경 생성 + 의존성 설치 + 서버 실행
# 또는 수동:
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/uvicorn backend.main:app --reload --port 8000
```

브라우저에서 http://localhost:8000 접속.

## koft.app 배포

`koft.app` 도메인 연결용 nginx/systemd 템플릿은 `deploy/` 폴더에 있습니다.
서버 배포 후 DNS에서 `koft.app`의 A 레코드를 서버 공인 IP로 지정하고,
`www.koft.app`은 `koft.app`으로 CNAME 연결하세요. 자세한 절차는
`deploy/README.md`를 참고하세요.

Vercel로 빠르게 MVP를 배포하려면 `pyproject.toml`, `vercel.json`,
`.vercelignore` 설정을 그대로 사용하면 됩니다. Vercel용 DNS/배포 절차와
서버리스 한계는 `deploy/VERCEL.md`를 참고하세요.

## 라이선스

이 프로젝트는 오픈소스가 아닙니다. `LICENSE`와 `NOTICE.md`에 명시된 대로
Futuremine97 (Koft)의 독점 저작물이며, 사전 서면 허가 없는 복제, 수정, 배포,
호스팅, 상업적 사용, 파생 저작물 제작을 허용하지 않습니다.

## 재구성 엔진

| 엔진 | 설명 | 요구사항 |
|---|---|---|
| **VGGT** (권장) | Meta의 CVPR 2025 SoTA. 사진 몇 장 → feed-forward 1회 추론으로 dense 3D 복원. NeRF/3DGS와 달리 장면별 학습 불필요 → 희소 뷰에 최적 | `torch` + `vggt` 설치, GPU 권장 |
| **NeRF / Volumetric** | 외부 NeRF API가 등록되면 API를 사용하고, 없으면 로컬 volumetric proxy로 앱 파이프라인 검증 | 실제 품질은 외부 NeRF/GPU API 권장 |
| **Voxel** | 포인트클라우드를 점유 voxel surface mesh로 변환해 STL/OBJ 다운로드 지원 | 기본 내장 |
| **외부 AI API** | `KOFT_AI_MODELS_JSON` 또는 `KOFT_RECON_API_URL`로 여러 3D/NeRF 모델 연결 | API endpoint + key |
| **데모** (기본 폴백) | 사진 시드 기반 통계적 파라메트릭 발 모델. GPU 없이 즉시 동작, 파이프라인/UI 검증용 | 없음 |

VGGT 설치 (선택):

```bash
./.venv/bin/pip install torch torchvision
./.venv/bin/pip install git+https://github.com/facebookresearch/vggt.git
```

최초 실행 시 HuggingFace에서 가중치(~5GB) 자동 다운로드. 설치되어 있으면
`auto` 엔진이 자동으로 VGGT를 사용합니다.

> 왜 NeRF가 아닌가: NeRF/Gaussian Splatting은 수십 장 + 장면별 최적화(수분~수십분)가
> 필요합니다. VGGT/DUSt3R 계열 feed-forward 모델이 "사진 몇 장" 시나리오의 현 SoTA입니다.

외부 AI 모델 API 연결 예시:

```bash
export KOFT_AI_MODELS_JSON='{"nerf_cloud":{"url":"https://api.example.com/nerf","api_key_env":"NERF_API_KEY","kind":"nerf"},"mesh_api":{"url":"https://api.example.com/reconstruct","api_key_env":"MESH_API_KEY","kind":"reconstruction"}}'
export NERF_API_KEY="..."
export MESH_API_KEY="..."
```

API 응답은 최소 `{"points":[[x,y,z],...]}` 형식이어야 하며, 선택적으로
`{"mesh":{"vertices":[...],"faces":[...]}}`를 포함할 수 있습니다.

## LiDAR (on/off)

사이드바 토글로 켜고 끕니다. `.ply` / `.json`(`{"points":[[x,y,z],...]}`) / `.xyz` 지원
(iPhone Pro 3D 스캐너 앱 내보내기 등). LiDAR는 절대 스케일(미터)을 제공하므로
사진 기반 결과의 스케일이 LiDAR 기준으로 보정됩니다.

스케일 우선순위: **LiDAR > 실측 발 길이 입력 > 엔진 추정**

## 파이프라인

```
사진들 ─┬─→ [VGGT | 데모] → 포인트클라우드 ─→ PCA 정렬/스케일 보정
LiDAR ──┘ (선택 융합)                          │
                                              ▼
                          측정 (길이·폭·발등·아치·둘레) → 아치 유형
                                              │
                                              ▼
              사이즈/핏 추천 (KR/US/EU/UK, 발볼 등급, 핏 노트)
                                              │
                                              ▼
              저작물/제작 등급 (데이터 신뢰·핏·보행·프린트 준비도)
                                              │
                                              ▼
        Inverse Design: 라스트 → 신발(갑피+밑창) → 커스텀 인솔(아치서포트+힐컵)
                                              │
                                              ▼
                        3D 뷰어 + STL/OBJ/PLY 다운로드
```

## API

- `GET /api/status` — 엔진 가용성
- `POST /api/reconstruct` — multipart: `photos[]`, `lidar`(선택), `use_lidar`, `engine`(auto|vggt|nerf|voxel|api|demo), `api_model`, `voxel_resolution`, `fit`, `true_length_mm`(선택)
- `GET /api/export/{result_id}/{kind}.{fmt}` — kind: foot|toes|voxels|last|shoe|insole|points, fmt: stl|obj|ply
  - 디자인 브리프: `kind=design`, `fmt=json`

## 구조

```
backend/
  main.py                  # FastAPI 서버
  meshutil.py              # 로프트/오프셋/병합 메쉬 유틸
  reconstruction/
    engine.py              # 오케스트레이터 (엔진 선택·LiDAR 융합·정렬·스케일)
    vggt_engine.py         # VGGT 실제 추론 (선택 설치)
    nerf_engine.py         # NeRF/volumetric proxy 및 API 폴백
    api_engine.py          # 외부 AI 모델 API 어댑터
    voxel.py               # 점유 voxel mesh 변환
    demo_engine.py         # 파라메트릭 폴백
    lidar.py               # PLY/JSON/XYZ 파서 + 융합
  analysis/
    measurements.py        # 발 측정치 추출
    sizing.py              # 사이즈/핏 추천
  design/
    last.py / shoe.py / insole.py / export.py   # inverse design + STL/OBJ
frontend/
  index.html / app.js / style.css               # Three.js 뷰어 UI
```

## 한계 (정직한 고지)

- 데모 엔진의 형상은 통계 모델이며 실측이 아닙니다. 정확한 측정에는 VGGT + 실측 길이 입력 또는 LiDAR가 필요합니다.
- VGGT 결과는 스케일이 상대적이므로 LiDAR 또는 실측 길이 입력을 권장합니다.
- 발 분리(segmentation)는 휴리스틱입니다. 단색 바닥에서 발만 나오게 찍으면 좋습니다.

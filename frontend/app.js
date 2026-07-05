import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// ---------- Three.js 씬 ----------
const wrap = document.getElementById('canvasWrap');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0f1117);
const camera = new THREE.PerspectiveCamera(45, 1, 0.001, 10);
camera.position.set(0.32, -0.30, 0.22);
camera.up.set(0, 0, 1);
const renderer = new THREE.WebGLRenderer({ antialias: true });
wrap.appendChild(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0.13, 0, 0.04);
controls.enableDamping = true;

scene.add(new THREE.AmbientLight(0xffffff, 0.55));
const key = new THREE.DirectionalLight(0xffffff, 1.1); key.position.set(0.5, -0.6, 1); scene.add(key);
const fill = new THREE.DirectionalLight(0x88aaff, 0.4); fill.position.set(-0.5, 0.6, 0.3); scene.add(fill);
const grid = new THREE.GridHelper(1, 40, 0x2a2f40, 0x1c2030);
grid.rotation.x = Math.PI / 2; scene.add(grid);

function resize() {
  const w = wrap.clientWidth, h = wrap.clientHeight;
  camera.aspect = w / h; camera.updateProjectionMatrix();
  renderer.setSize(w, h); renderer.setPixelRatio(devicePixelRatio);
}
new ResizeObserver(resize).observe(wrap); resize();
(function animate() { requestAnimationFrame(animate); controls.update(); renderer.render(scene, camera); })();

// ---------- 모델 그룹 ----------
const groups = {};
for (const name of ['points', 'foot', 'toes', 'voxels', 'last', 'shoe', 'insole']) {
  groups[name] = new THREE.Group(); groups[name].visible = false; scene.add(groups[name]);
}

const MATS = {
  foot: new THREE.MeshStandardMaterial({ color: 0xd9a066, roughness: 0.7, side: THREE.DoubleSide }),
  toes: new THREE.MeshStandardMaterial({ color: 0xf2c08f, roughness: 0.68, side: THREE.DoubleSide }),
  voxels: new THREE.MeshStandardMaterial({ color: 0x9d7cff, roughness: 0.58, side: THREE.DoubleSide }),
  last: new THREE.MeshStandardMaterial({ color: 0x5b8cff, roughness: 0.45, side: THREE.DoubleSide }),
  shoe: new THREE.MeshStandardMaterial({ color: 0x35d0a5, roughness: 0.55, side: THREE.DoubleSide }),
  insole: new THREE.MeshStandardMaterial({ color: 0xff8a5b, roughness: 0.6, side: THREE.DoubleSide }),
};

function setMesh(name, meshData, opacity = 1) {
  const g = groups[name]; g.clear();
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(meshData.vertices, 3));
  geo.setIndex(meshData.faces);
  geo.computeVertexNormals();
  const mat = MATS[name].clone();
  if (opacity < 1) { mat.transparent = true; mat.opacity = opacity; }
  g.add(new THREE.Mesh(geo, mat));
}

function setPoints(flat) {
  const g = groups.points; g.clear();
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(flat, 3));
  const n = flat.length / 3;
  const colors = new Float32Array(n * 3);
  let zMin = Infinity, zMax = -Infinity;
  for (let i = 0; i < n; i++) { const z = flat[i * 3 + 2]; if (z < zMin) zMin = z; if (z > zMax) zMax = z; }
  const c = new THREE.Color();
  for (let i = 0; i < n; i++) {
    const t = (flat[i * 3 + 2] - zMin) / (zMax - zMin + 1e-9);
    c.setHSL(0.62 - t * 0.5, 0.85, 0.35 + t * 0.3);
    colors.set([c.r, c.g, c.b], i * 3);
  }
  geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  g.add(new THREE.Points(geo, new THREE.PointsMaterial({ size: 0.0016, vertexColors: true })));
}

// ---------- 탭 ----------
let currentView = 'points';
function showView(v) {
  currentView = v;
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.view === v));
  for (const k in groups) groups[k].visible = false;
  if (v === 'overlay') {
    groups.foot.visible = groups.shoe.visible = true;
    groups.foot.children.forEach(m => { m.material.transparent = true; m.material.opacity = 0.9; });
    groups.shoe.children.forEach(m => { m.material.transparent = true; m.material.opacity = 0.35; });
  } else if (groups[v]) {
    groups[v].visible = true;
    groups[v].children.forEach(m => { if (m.material && m.material.opacity !== undefined && v !== 'points') { m.material.transparent = false; m.material.opacity = 1; } });
  }
}
document.querySelectorAll('.tab').forEach(t => t.onclick = () => showView(t.dataset.view));

// ---------- 업로드 UI ----------
const dz = document.getElementById('dropzone');
const photoInput = document.getElementById('photos');
const thumbs = document.getElementById('thumbs');
const runBtn = document.getElementById('runBtn');
let files = [];

dz.onclick = () => photoInput.click();
dz.ondragover = e => { e.preventDefault(); dz.classList.add('drag'); };
dz.ondragleave = () => dz.classList.remove('drag');
dz.ondrop = e => { e.preventDefault(); dz.classList.remove('drag'); addFiles(e.dataTransfer.files); };
photoInput.onchange = () => addFiles(photoInput.files);

function addFiles(list) {
  for (const f of list) if (f.type.startsWith('image/') && files.length < 8) files.push(f);
  thumbs.innerHTML = '';
  for (const f of files) {
    const img = document.createElement('img');
    img.src = URL.createObjectURL(f);
    thumbs.appendChild(img);
  }
  runBtn.disabled = files.length < 2;
}

document.getElementById('useLidar').onchange = e =>
  document.getElementById('lidarBox').classList.toggle('hidden', !e.target.checked);

// ---------- 엔진 상태 ----------
const badge = document.getElementById('engineBadge');
fetch('/api/status').then(r => r.json()).then(s => {
  badge.classList.remove('hidden');
  const apiCount = (s.external_models || []).length;
  badge.textContent = s.vggt_available
    ? `엔진: VGGT + NeRF/Voxel + API ${apiCount}개`
    : `엔진: 데모 + NeRF/Voxel + API ${apiCount}개`;
});

// ---------- 실행 ----------
const statusMsg = document.getElementById('statusMsg');
const SERVERLESS_UPLOAD_LIMIT_BYTES = 4.2 * 1024 * 1024;

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

function loadImage(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('image decode failed')); };
    img.src = url;
  });
}

function compressedName(name) {
  const base = name.replace(/\.[^/.]+$/, '') || 'photo';
  return `${base}-optimized.jpg`;
}

async function compressImage(file, maxDim = 1280, quality = 0.74, force = false) {
  if (!file.type.startsWith('image/') || (!force && file.size <= 900 * 1024)) return file;
  try {
    const img = await loadImage(file);
    const scale = Math.min(1, maxDim / Math.max(img.naturalWidth, img.naturalHeight));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(img.naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(img.naturalHeight * scale));
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', quality));
    if (!blob || (!force && blob.size >= file.size)) return file;
    return new File([blob], compressedName(file.name), {
      type: 'image/jpeg',
      lastModified: file.lastModified,
    });
  } catch {
    return file;
  }
}

async function preparePhotosForUpload(sourceFiles) {
  const originalBytes = sourceFiles.reduce((sum, f) => sum + f.size, 0);
  let prepared = [];
  for (const f of sourceFiles) prepared.push(await compressImage(f));

  let optimizedBytes = prepared.reduce((sum, f) => sum + f.size, 0);
  if (optimizedBytes > SERVERLESS_UPLOAD_LIMIT_BYTES) {
    prepared = [];
    for (const f of sourceFiles) prepared.push(await compressImage(f, 960, 0.64, true));
    optimizedBytes = prepared.reduce((sum, f) => sum + f.size, 0);
  }
  if (optimizedBytes > SERVERLESS_UPLOAD_LIMIT_BYTES) {
    prepared = [];
    for (const f of sourceFiles) prepared.push(await compressImage(f, 760, 0.56, true));
    optimizedBytes = prepared.reduce((sum, f) => sum + f.size, 0);
  }

  return { files: prepared, originalBytes, optimizedBytes };
}

runBtn.onclick = async () => {
  runBtn.disabled = true;
  statusMsg.classList.remove('error');
  statusMsg.textContent = '사진 최적화 중…';

  try {
    const prepared = await preparePhotosForUpload(files);
    if (prepared.optimizedBytes > SERVERLESS_UPLOAD_LIMIT_BYTES) {
      throw new Error('업로드 용량이 큽니다. 사진 수를 줄이거나 해상도를 낮춰 다시 시도하세요.');
    }

    const fd = new FormData();
    prepared.files.forEach(f => fd.append('photos', f));
    const useLidar = document.getElementById('useLidar').checked;
    fd.append('use_lidar', useLidar);
    const lf = document.getElementById('lidarFile').files[0];
    if (useLidar && lf) fd.append('lidar', lf);
    fd.append('engine', document.getElementById('engine').value);
    const apiModel = document.getElementById('apiModel').value.trim();
    if (apiModel) fd.append('api_model', apiModel);
    fd.append('voxel_resolution', document.getElementById('voxelResolution').value || '32');
    fd.append('fit', document.getElementById('fit').value);
    const tl = document.getElementById('trueLen').value;
    if (tl) fd.append('true_length_mm', tl);

    statusMsg.textContent =
      `재구성 중… (${formatBytes(prepared.originalBytes)} → ${formatBytes(prepared.optimizedBytes)})`;
    const res = await fetch('/api/reconstruct', { method: 'POST', body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const data = await res.json();
    render(data);
    statusMsg.textContent = data.note || '완료';
  } catch (e) {
    statusMsg.classList.add('error');
    statusMsg.textContent = '오류: ' + e.message;
  } finally {
    runBtn.disabled = false;
  }
};

// ---------- 결과 렌더 ----------
function render(d) {
  setPoints(d.points);
  setMesh('foot', d.meshes.foot);
  setMesh('toes', d.meshes.toes);
  setMesh('voxels', d.meshes.voxels);
  setMesh('last', d.meshes.last);
  setMesh('shoe', d.meshes.shoe);
  setMesh('insole', d.meshes.insole);
  showView('points');

  badge.textContent = `엔진: ${d.engine_used.toUpperCase()} · 스케일: ${d.scale_source}` +
    (d.lidar_used ? ' · LiDAR 융합 ON' : '') + ` · 사진 ${d.n_photos}장`;

  const m = d.measurements;
  const pct = v => Math.round((v || 0) * 100) + '%';
  const items = [
    ['발 길이', m.foot_length_mm + ' mm'],
    ['발볼 폭', m.ball_width_mm + ' mm'],
    ['뒤꿈치 폭', m.heel_width_mm + ' mm'],
    ['발등 높이', m.instep_height_mm + ' mm'],
    ['아치 높이', m.arch_height_mm + ' mm'],
    ['발볼 둘레', m.ball_girth_mm + ' mm'],
    ['아치 유형', { flat: '낮음(평발 경향)', normal: '보통', high: '높음' }[m.arch_type]],
    ['포인트 수', m.n_points.toLocaleString()],
  ];
  document.getElementById('measGrid').innerHTML = items.map(([k, v]) =>
    `<div class="card"><div class="k">${k}</div><div class="v">${v}</div></div>`).join('');

  const toeRecon = d.toe_reconstruction || {};
  document.getElementById('toeReconGrid').innerHTML = (toeRecon.toes || []).map(t =>
    `<div class="card toe-card"><div class="k">${t.label}</div><div class="v">${t.length_mm} mm</div><div class="meta">폭 ${t.width_mm} mm · 높이 ${t.height_mm} mm · 신뢰 ${pct(t.confidence)}</div></div>`).join('');

  const vox = d.voxel_reconstruction || {};
  const modelInfo = d.model_info || {};
  const voxelItems = [
    ['점유 Voxel', `${(vox.occupied || 0).toLocaleString()}개`],
    ['Voxel 크기', `${vox.voxel_size_mm ?? 0} mm`],
    ['해상도', `${vox.resolution || 0}³`],
    ['모델 정보', modelInfo.id ? `${modelInfo.kind || 'api'} · ${modelInfo.id}` : (modelInfo.type || d.engine_used)],
  ];
  document.getElementById('voxelGrid').innerHTML = voxelItems.map(([k, v]) =>
    `<div class="card voxel-card"><div class="k">${k}</div><div class="v small">${v}</div><div class="meta">${k === '점유 Voxel' ? `신뢰 ${pct(vox.confidence)}` : ''}</div></div>`).join('');

  const det = m.detections || {};
  const rotation = det.rotation || {};
  const hallux = det.hallux_valgus || {};
  const detectionItems = [
    [
      '내/외회전',
      rotation.label || '판정 불가',
      `${rotation.angle_deg ?? 0}° · 신뢰 ${pct(rotation.confidence)}`,
      rotation.severity || 'unknown',
    ],
    [
      '무지외반증',
      hallux.label || '판정 불가',
      `${hallux.angle_deg ?? 0}° · 신뢰 ${pct(hallux.confidence)}`,
      hallux.severity || 'unknown',
    ],
  ];
  document.getElementById('detectionGrid').innerHTML = detectionItems.map(([k, v, meta, severity]) =>
    `<div class="card detect ${severity}"><div class="k">${k}</div><div class="v">${v}</div><div class="meta">${meta}</div></div>`).join('');

  const fitCheck = d.fit_assessment || {};
  const fitClass = fitCheck.verdict || 'unknown';
  document.getElementById('fitCheckSummary').innerHTML = `
    <div class="fit-main ${fitClass}">
      <div class="fit-title">${fitCheck.label || '판정 불가'}</div>
      <div class="fit-copy">목표 여유 ${fitCheck.target_clearance_mm ?? 0}mm · 외측 여유 ${fitCheck.pinky_lateral_clearance_mm ?? 0}mm · 돌출 ${fitCheck.pinky_prominence_mm ?? 0}mm</div>
      <div class="fit-copy">추천 외측 relief +${fitCheck.recommended_pinky_relief_mm ?? 0}mm · 신뢰 ${pct(fitCheck.confidence)}</div>
      <div class="fit-recs">${(fitCheck.recommendations || []).map(x => `<span>${x}</span>`).join('')}</div>
    </div>`;
  document.getElementById('fitZoneGrid').innerHTML = (fitCheck.zones || []).map(z =>
    `<div class="card detect ${z.status || 'unknown'}"><div class="k">${z.name}</div><div class="v">${z.clearance_mm} mm</div><div class="meta">목표 ${z.target_mm} mm</div></div>`).join('');

  const dyn = d.dynamic_simulation || {};
  const metric = dyn.metrics || {};
  const dynClass = dyn.grade || 'unknown';
  document.getElementById('dynamicSummary').innerHTML = `
    <div class="dynamic-main ${dynClass}">
      <div class="dynamic-score">${dyn.overall_score ?? 0}</div>
      <div>
        <div class="dynamic-title">동적 편안함 ${dynClass === 'good' ? '양호' : dynClass === 'watch' ? '주의' : '개선 필요'}</div>
        <div class="dynamic-copy">신뢰 ${pct(dyn.confidence)} · ${(dyn.notes || []).join(' · ')}</div>
      </div>
    </div>`;
  const dynamicMetrics = [
    ['착지 충격', metric.impact_peak],
    ['보행 안정성', metric.stability_score],
    ['앞볼 굴곡', metric.forefoot_flex_score],
    ['새끼발가락 전단', metric.pinky_shear_risk],
    ['밀어내기', metric.toe_off_score],
  ];
  document.getElementById('dynamicMetricGrid').innerHTML = dynamicMetrics.map(([k, v]) =>
    `<div class="card"><div class="k">${k}</div><div class="v">${v ?? 0}</div></div>`).join('');
  document.getElementById('gaitPhaseList').innerHTML = (dyn.phases || []).map(p => {
    const pressure = p.pressure || {};
    const bars = [
      ['뒤꿈치', pressure.heel],
      ['내측', pressure.medial],
      ['외측', pressure.lateral],
      ['앞볼', pressure.forefoot],
      ['새끼', pressure.fifth_toe],
    ].map(([label, value]) => `<div class="pressure-row"><span>${label}</span><b style="width:${Math.min(100, value || 0)}%"></b><em>${value ?? 0}</em></div>`).join('');
    return `<div class="phase-card">
      <div class="phase-head"><strong>${p.label}</strong><span>${p.stance_percent}</span><em>${p.comfort_score}</em></div>
      <div class="phase-note">${p.note}</div>
      <div class="pressure-bars">${bars}</div>
    </div>`;
  }).join('');

  const quality = d.artifact_quality || d.design?.artifact_quality || {};
  const qualityClass = quality.readiness || 'needs_refinement';
  document.getElementById('artifactQuality').innerHTML = `
    <div class="quality-main ${qualityClass}">
      <div class="quality-grade">${quality.grade || '-'}</div>
      <div>
        <div class="quality-title">${quality.label || '등급 산정 전'}</div>
        <div class="quality-copy">제작 준비도 ${quality.score ?? 0}점</div>
      </div>
    </div>
    <div class="quality-checks">
      ${(quality.checklist || []).map(c => `
        <div class="quality-check ${c.status || 'watch'}">
          <strong>${c.label}</strong>
          <span>${c.detail}</span>
        </div>`).join('')}
    </div>
    <div class="quality-notes">${(quality.notes || []).map(n => `<span>${n}</span>`).join('')}</div>`;

  const design = d.design || {};
  const material = design.material_stack || {};
  const texture = design.texture || {};
  const textureSystem = design.texture_system || {};
  const print = design.print_profile || {};
  document.getElementById('designSummary').innerHTML = `
    <div class="design-main">
      <div class="design-title">${design.design_name || 'Custom Shoe'}</div>
      <div class="design-copy">${design.silhouette || ''}</div>
      <div class="design-rationale">${(design.design_rationale || []).map(x => `<span>${x}</span>`).join('')}</div>
    </div>`;

  const materialItems = [
    ['갑피', material.upper],
    ['미드솔', material.midsole],
    ['아웃솔', material.outsole],
    ['인솔', material.insole],
  ].filter(([, v]) => v);
  document.getElementById('materialGrid').innerHTML = materialItems.map(([k, v]) =>
    `<div class="card"><div class="k">${k}</div><div class="v small">${v}</div></div>`).join('');

  const textureItems = [
    ['텍스처 프리셋', textureSystem.name || texture.upper],
    ['갑피 패턴', textureSystem.upper_pattern || texture.upper],
    ['아웃솔 패턴', textureSystem.outsole_pattern || texture.outsole],
    ['토박스', texture.toe_box],
    ['최소 피처', `${textureSystem.manufacturing?.min_feature_mm || '-'} mm`],
    ['프린트', `${print.recommended_process || ''} · ${print.infill || ''}`],
  ].filter(([, v]) => v);
  document.getElementById('textureGrid').innerHTML = textureItems.map(([k, v]) =>
    `<div class="card"><div class="k">${k}</div><div class="v small">${v}</div></div>`).join('');
  document.getElementById('textureZoneList').innerHTML = `
    <div class="texture-zone-head">
      <strong>${textureSystem.finish?.upper_surface || 'matte TPU texture'}</strong>
      <span>${textureSystem.finish?.colorway || ''}</span>
    </div>
    <div class="texture-zones">
      ${(textureSystem.zones || []).map(z => `
        <div class="texture-zone">
          <div><strong>${z.name}</strong><span>${z.pattern}</span></div>
          <em>${z.depth_mm}mm</em>
          <p>${z.purpose}</p>
        </div>`).join('')}
    </div>
    <div class="texture-print-note">${textureSystem.manufacturing?.print_note || ''}</div>`;

  document.getElementById('brandGrid').innerHTML = (design.brand_recommendations || []).map(b => `
    <a class="brand-card" href="${b.url}" target="_blank" rel="noopener">
      <div class="brand-score">${b.score}</div>
      <div>
        <div class="brand-name">${b.brand}</div>
        <div class="brand-line">${b.line}</div>
        <div class="brand-why">${b.why}</div>
        <div class="brand-tip">${b.fit_tip}</div>
      </div>
    </a>`).join('');

  const s = d.sizing, r = s.recommended;
  document.getElementById('sizeCards').innerHTML = `
    <div class="size-main"><div class="big">${r.kr_mm}</div>
      <div class="lab">추천 사이즈 (KR mm) · ${s.width_class} · 여유 +${s.allowance_mm}mm</div></div>
    <div class="size-sub"><div class="v">${r.us_men}</div><div class="k">US(M)</div></div>
    <div class="size-sub"><div class="v">${r.us_women}</div><div class="k">US(W)</div></div>
    <div class="size-sub"><div class="v">${r.eu}</div><div class="k">EU</div></div>
    <div class="size-sub"><div class="v">${r.uk}</div><div class="k">UK</div></div>`;
  document.getElementById('fitNotes').innerHTML =
    (s.fit_notes || []).map(n => `<div>${n}</div>`).join('');

  const rid = d.result_id;
  const dls = [
    ['완성 신발 STL', `shoe.stl`], ['완성 신발 OBJ', `shoe.obj`],
    ['발가락 STL', `toes.stl`], ['발가락 OBJ', `toes.obj`],
    ['Voxel STL', `voxels.stl`], ['Voxel OBJ', `voxels.obj`],
    ['디자인 JSON', `design.json`], ['라스트 STL', `last.stl`],
    ['인솔 STL', `insole.stl`], ['발 메쉬 STL', `foot.stl`],
    ['포인트 PLY', `points.ply`],
  ];
  document.getElementById('downloads').innerHTML = dls.map(([label, path]) =>
    `<a class="dl" href="/api/export/${rid}/${path}" download>${label}</a>`).join('');

  document.getElementById('results').classList.remove('hidden');
}

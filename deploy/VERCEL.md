# Vercel deployment for koft.app

Vercel is a good fit for an MVP/demo version of FootFit AI because it can run
the FastAPI app as one Python Function and handle HTTPS/domain routing for you.
For heavy VGGT inference, GPU workloads, very large images, or durable 3D export
storage, use a VPS/GPU server or object storage alongside Vercel.

## What is already configured

- `pyproject.toml` defines Python 3.12 project metadata and deployment
  dependencies for Vercel's Python runtime.
- `api/index.py` exposes the FastAPI app through Vercel's Python Function
  entrypoint.
- `vercel.json` routes all paths to that Function and sets the function duration
  to 300 seconds.
- `.python-version` selects Python 3.12.
- `.vercelignore` keeps local virtualenv/cache/server-only deploy files out of
  the deployment bundle.
- `frontend/app.js` compresses uploaded photos before submit so the request is
  less likely to exceed Vercel's payload limit.
- `backend/main.py` reduces viewer point-cloud output on Vercel to keep JSON
  responses smaller.

## Deploy

Install the Vercel CLI and deploy from the project root:

```bash
npm i -g vercel
vercel login
vercel
vercel --prod
```

When prompted, choose the current folder as the project root. Vercel will install
Python dependencies from `requirements.txt`.

## Domain setup for koft.app

1. In Vercel Dashboard, open the project and add these domains:
   - `koft.app`
   - `www.koft.app`
2. In Sav/DNS settings, remove the current parking A records.
3. Add the DNS records Vercel shows in the dashboard. Current Vercel
   verification recommends:

```text
@     A      216.198.79.1
@     A      64.29.17.1
www   CNAME  b83491e0ead07f42.vercel-dns-017.com
```

Use the exact records Vercel displays if they differ.

Alternatively, switch nameservers at Sav to Vercel DNS:

```text
ns1.vercel-dns.com
ns2.vercel-dns.com
```

## Important limits

- Vercel's Python Runtime is beta.
- A FastAPI app is deployed as a single Vercel Function.
- Function payloads are limited, so very large photo uploads or huge JSON mesh
  responses can fail. This app now compresses browser uploads and down-samples
  viewer points on Vercel.
- `RESULTS` is in memory. On serverless infrastructure, export links may expire
  or hit a different instance. For production, move generated STL/OBJ/JSON files
  to Vercel Blob, S3, R2, or another durable store.
- VGGT with GPU and multi-GB model weights is not a good Vercel Function fit.
  Keep `engine=demo` on Vercel, or call a separate GPU inference server.
- If you want the strongest code-level protection, keep the GitHub repository
  private and grant Vercel read access during project import.

## Verify

```bash
curl https://koft.app/api/status
```

Then open:

```text
https://koft.app/
```

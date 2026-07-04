# koft.app deployment

This folder contains production templates for serving FootFit AI on
`https://koft.app`.

## Current DNS check

At the time this file was added, `koft.app` was still using Sav coming-soon
nameservers:

```text
ns1-coming-soon.sav.com
ns2-coming-soon.sav.com
```

The apex and `www` records were resolving to parking-page IPs, not this app.

## DNS records to set

In the DNS provider for `koft.app`, set:

```text
koft.app      A      <YOUR_SERVER_PUBLIC_IPV4>
www.koft.app  CNAME  koft.app
```

If your DNS provider does not allow CNAME at `www`, use another A record:

```text
www.koft.app  A      <YOUR_SERVER_PUBLIC_IPV4>
```

## Server setup

Assuming the project lives at `/opt/3d_shoes`:

### One-command Ubuntu setup

Copy this project folder to the server first, then run from the project root:

```bash
chmod +x deploy/setup_ubuntu.sh
./deploy/setup_ubuntu.sh
```

After DNS points to the server, enable HTTPS:

```bash
ENABLE_HTTPS=1 CERTBOT_EMAIL=you@example.com ./deploy/setup_ubuntu.sh
```

### Manual setup

Assuming the project lives at `/opt/3d_shoes`:

```bash
cd /opt/3d_shoes
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

Install the service:

```bash
sudo cp deploy/footfit-ai.service /etc/systemd/system/footfit-ai.service
sudo systemctl daemon-reload
sudo systemctl enable --now footfit-ai
```

Install nginx reverse proxy:

```bash
sudo cp deploy/koft.app.nginx.conf /etc/nginx/sites-available/koft.app
sudo ln -s /etc/nginx/sites-available/koft.app /etc/nginx/sites-enabled/koft.app
sudo nginx -t
sudo systemctl reload nginx
```

Enable HTTPS after DNS points to the server:

```bash
sudo certbot --nginx -d koft.app -d www.koft.app
```

## Verify

```bash
curl -I https://koft.app/
curl https://koft.app/api/status
```

## Vercel option

If you prefer Vercel instead of a VPS, see `deploy/VERCEL.md`.
The app includes `pyproject.toml`, `vercel.json`, `.python-version`, and
`.vercelignore` for a FastAPI deployment on Vercel.

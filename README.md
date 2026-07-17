# Workyard API Client + Dashboard

Standalone integration with the [Workyard REST API](https://developers.workyard.com)
for Hardman Signs (org 45770). Not wired into WorkOrderHub or ATLAS — this is a
self-contained tool for viewing and managing Workyard data.

## Setup

```
pip install -r requirements.txt      # or reuse WorkOrderHub's .venv — it has everything
```

`.env` (gitignored) must contain:

```
WORKYARD_API_TOKEN=<Bearer token from Workyard dashboard -> Integrations -> API Token>
WORKYARD_ORG_ID=45770
```

## Run the dashboard

```
.\run-workyard.ps1
.\run-workyard.ps1 --serve-https   # Tailscale Serve HTTPS (phone rapid camera)
# or: python app.py
```

- Listens on **port 5210**, bound to `0.0.0.0` (plain HTTP).
- PC browser: `http://127.0.0.1:5210`
- Overrides: `WORKYARD_HOST`, `WORKYARD_PORT`

### Phone access (Tailscale)

1. Install/sign in to [Tailscale](https://tailscale.com/) on this PC and the phone (same tailnet).
2. Start the dashboard with `.\run-workyard.ps1`.
3. Pick one of:

| Mode | How | Phone URL | Camera |
|------|-----|-----------|--------|
| Plain HTTP | default run | `http://<pc-tailscale-ip>:5210` | One shot at a time (OS camera) |
| HTTPS via Serve | `.\run-workyard.ps1 --serve-https` | printed `https://<machine>.….ts.net` | Rapid in-page multi-shot |

`--serve-https` runs `tailscale serve` so Tailscale terminates TLS with a trusted cert
and proxies to local `http://127.0.0.1:5210`. The app itself stays HTTP-only (no
self-signed Flask certs). Stop Serve later with:

```
tailscale serve reset
```

Safari/Chrome on iPhone only allow live `getUserMedia` camera in a **secure context**
(HTTPS). Switching browsers does not bypass that — use `--serve-https`.

## Features

- **Browse** — Employees, Projects, Customers, Time Cards, Tasks, Time Off, Tags,
  Geofences, Smart Forms, Cost Codes (per project). Filters + pagination; click a
  row for the full JSON record.
- **Final Assembly** — finds smart forms titled exactly `Final Assembly Checklist`,
  lists submissions (date / employee / Job ID filters), and opens a readable
  checklist view with photos and signature. Use **New submission** to fill out
  and POST a live checklist. Use **Open camera** for multi-shot capture (or library);
  photos are resized client-side as data URLs. Mobile-friendly layout (hamburger
  nav, full-screen detail drawer, touch-sized controls). From **Smart Forms**, use
  **View submissions** on any form for the same list/detail experience (and New
  submission when that form is loaded).
- **API Console** — send POST/PUT/PATCH/DELETE requests to any resource under
  `/orgs/{org_id}/`. **These are live writes to the real Workyard org.**

## Use the client directly

```python
from client import WorkyardClient

wy = WorkyardClient()                     # reads .env vars from process env
wy.employees()                            # first page
list(wy.paginate('time_cards'))           # all records, auto-paged
wy.patch('tasks/123', json={'status': 'done'})
```

- Auth: `Authorization: Bearer <token>`; 60 req/min rate limit — the client
  sleeps and retries automatically on HTTP 429 (`Retry-After` header).
- List endpoints paginate with `limit` / `page`; responses are `{"data": [...]}`.
- Some GET endpoints allow only one in-flight request per API user.
- `openapi.json` is the full spec (54 endpoints), downloaded from
  https://developers.workyard.com/public-api-docs.json

## Files

```
client.py               WorkyardClient — auth, retries, pagination, resource helpers
app.py                  Flask dashboard (port 5210, HTTP)
run-workyard.ps1        Launcher; optional --serve-https (Tailscale Serve)
templates/dashboard.html
openapi.json            Workyard OpenAPI spec (reference)
requirements.txt
```

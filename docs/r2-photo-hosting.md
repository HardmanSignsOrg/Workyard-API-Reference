# Cloudflare R2 photo hosting (optional)

When configured, Final Assembly / Smart Form photos are uploaded to your R2
bucket as public HTTPS URLs, then referenced in the Workyard submission.
That avoids Workyard's ~200KB embedded data-URL limit. Objects are never
auto-deleted.

## Cloudflare dashboard

1. Create a free Cloudflare account → **R2**.
2. Create a bucket (e.g. `workyard-photos`). Do **not** add a delete lifecycle.
3. Bucket **Settings** → enable **Public access** → copy the public URL
   (e.g. `https://pub-….r2.dev`).
4. **R2 → Overview → Manage R2 API Tokens** → create a token with
   **Object Read & Write** on that bucket. Copy Access Key ID + Secret + Account ID.

## `.env` (gitignored)

```
R2_ACCOUNT_ID=<from R2 overview sidebar>
R2_ACCESS_KEY_ID=<API token access key id>
R2_SECRET_ACCESS_KEY=<API token secret>
R2_BUCKET=workyard-photos
R2_PUBLIC_BASE_URL=https://pub-b384151765cc44b2873ae301328d793c.r2.dev
```

No trailing slash on `R2_PUBLIC_BASE_URL`.

## Verify

```
pip install -r requirements.txt
.\run-workyard.ps1
```

Open the dashboard → browser console or hit `http://127.0.0.1:5210/api/media/status`
— should show `"enabled": true`. Submit a checklist with several photos; they
should land under `final-assembly/YYYY/MM/DD/…` in the bucket and appear in Workyard.

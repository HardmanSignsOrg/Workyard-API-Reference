# Final Assembly Checklist — Smart Form Submissions Viewer

**Date:** 2026-07-17  
**Repo:** workyard (standalone Workyard API dashboard)  
**Status:** Approved design

## Goal

Let Hardman Signs staff browse and review **Final Assembly Checklist** smart form submissions in a readable QA layout (answers, photos, signature), with date / employee / Job ID filters. Also support the same submissions flow for **any** smart form from the existing Smart Forms browser.

## Context

- Workyard org `45770`; Flask dashboard on port `5210` (`app.py`, `client.py`, `templates/dashboard.html`).
- Relevant API:
  - `GET /orgs/{org_id}/smart_forms` — list/search forms (`search`, `status`, pagination)
  - `GET /orgs/{org_id}/smart_forms/{form_id}/submissions` — submission list (metadata only)
  - `GET /orgs/{org_id}/smart_forms/{form_id}/submissions/{submission_id}` — full detail (`response_data`, form structure, files)
- Known form today: id `5376`, title `Final Assembly Checklist`, published. Answer fields include `projectName` (Job ID), photo upload, boolean pass/fail, notes, inspector name, signature, datetime.
- Existing dashboard already lists Smart Forms but has no submissions drill-down.
- Client already caches GETs (45s TTL) and retries HTTP 429.

## Approach

**Frontend-heavy (Approach A):** extend the dashboard UI; keep using `/api/get/<resource>` for upstream calls. No new write APIs. Add a small optional backend enrichment endpoint only if Job ID enrichment becomes too chatty for the UI — prefer doing enrichment in the browser with the existing cache first.

## Product behavior

### 1. Nav: “Final Assembly”

- New sidebar item under resources/ops (same visual language as existing views).
- Resolves forms where `title` equals `Final Assembly Checklist` (trim + case-insensitive). Prefer `search=final assembly checklist` then exact-filter client-side so unrelated fuzzy matches are dropped.
- **Multiple matches:** merge submissions from all matching forms into one list, showing a Form ID column only when more than one form is present. Do not require the user to pick a form first.
- **Zero matches:** empty state with a clear message (form missing / unpublished / title changed).

### 2. Submissions table

Columns (newest `completed_at` first):

| Column | Source |
|--------|--------|
| Completed | `completed_at` (unix → local datetime) |
| Employee | `created_by_employee.display_name` |
| Job ID | from detail `response_data.projectName` (enriched) |
| Signs OK | from detail `response_data.question3` (boolean → Yes/No) |
| Photos | `has_file_attachment` or enriched photo count |
| Flags | `unexpected_answers_count` if > 0 |

Clicking a row opens the detail view for that submission.

### 3. Filters

- **Completed from / to** — map to API `completed_at_from` / `completed_at_to` (unix).
- **Employee** — filter by employee id when numeric; otherwise filter list rows by display name contains (client-side). Prefer API `created_by_employee_id` when an id is known.
- **Job ID** — client-side contains match on enriched `projectName`. Requires detail (or enrichment pass) for listed rows.

### 4. Submission detail (readable checklist)

Dedicated panel/drawer (not raw-JSON-first):

1. Header: form title, submission id, completed time, employee.
2. Fields in form order from `form_version.structure` (SurveyJS-style pages/elements), using `response_data` + element titles:
   - text / datetime → plain text
   - boolean → Yes/No (respect display intent; no chip overload)
   - file → thumbnail grid; click opens full image in new tab (signed S3 URLs)
   - signaturepad → render image (data URL or hosted URL as returned)
3. Footer metadata: related entity (if any), unexpected answers, version ids.
4. Collapsed “Raw JSON” toggle for debugging.

For Final Assembly specifically, field names above are the current schema; the renderer must be **structure-driven** so other forms and future checklist revisions still display correctly.

### 5. Smart Forms enhancement

- Keep existing Smart Forms list/search.
- Per-row (or row-click secondary action): **View submissions** → same submissions table + detail UI bound to that `form_id` (and that form’s title in the header).
- Final Assembly board is a convenience entry point; Smart Forms remains the general path.

## Data flow

```
Final Assembly view
  → GET smart_forms?search=...&all=1
  → exact title filter
  → for each form_id: GET smart_forms/{id}/submissions (...filters, paginate/all)
  → merge + sort by completed_at desc
  → enrich visible/filtered rows: GET smart_forms/{id}/submissions/{sid}
       (parse response_data JSON string → Job ID, Signs OK, etc.)
  → apply Job ID filter client-side
  → on row open: use cached detail or fetch once → render checklist

Smart Forms → View submissions
  → same submissions UI with fixed form_id (skip title resolve)
```

### Enrichment / rate limits

- Workyard limit: 60 req/min; client already sleeps on 429.
- Dashboard GET cache (45s) applies via `/api/get`.
- Enrichment strategy: enrich after list load for current page / current result set; show table skeleton with metadata first, fill Job ID / Signs OK as details arrive. Do not block the whole table on every detail.
- If result sets grow large, enrich only the current page (default page size aligned with existing dashboard, e.g. 50) before applying Job ID filter on that page — document that Job ID filter is most accurate after “Load all” + enrichment completes. Prefer: when Job ID filter is non-empty, fetch-all submissions for the form(s), enrich all, then filter (user explicitly opted into a search that needs answers). Cap with a practical warning if submission count is very high (e.g. > 200) rather than building a new backend.

## UI placement

- Reuse existing dashboard CSS variables, toolbar, table, drawer/modal patterns already in `dashboard.html`.
- New view mode in the SPA state machine (alongside `overview`, resource browse, etc.).
- No new visual design system; match current Workyard Ops look.

## Out of scope

- Creating/editing submissions
- Approving workflows beyond viewing
- CSV export of answers (existing generic CSV export may still work on list endpoints; answer-flattened export is a follow-up)
- Wiring into WorkOrderHub / ATLAS
- Changing form definitions in Workyard

## Error handling

- API errors: show status message in the existing `.status-msg.err` pattern; keep last good data if any.
- Missing/malformed `response_data` or `structure`: show available metadata + raw JSON; skip broken fields without crashing.
- Expired photo URLs: broken-image placeholder; user can refresh detail to re-fetch signed URLs.

## Testing / verification

- Manual: open Final Assembly → see submissions for form 5376 → open detail → photos + signature render.
- Filters: date range hits API; employee name filters list; Job ID contains filters enriched rows.
- Smart Forms → View submissions on the same form yields equivalent detail.
- With `_refresh=1` / Refresh control, cache bypass works as elsewhere.
- Confirm rate-limit behavior with enrichment (no dashboard freeze; 429s recover).

## Files likely touched

- `templates/dashboard.html` — nav, Final Assembly view, submissions table, checklist detail renderer, Smart Forms action
- `app.py` — only if a thin enrichment helper proves necessary (default: none)
- `client.py` — optional convenience helpers (`smart_form_submissions`, etc.); not required if UI uses generic `get`
- `README.md` — short note on Final Assembly + submissions viewing

## Success criteria

1. From the dashboard, a user can open **Final Assembly**, see all matching-form submissions, filter by date/employee/Job ID, and review a readable checklist with photos and signature.
2. From **Smart Forms**, a user can open submissions for any form with the same detail experience.
3. No live writes; read-only against Workyard.

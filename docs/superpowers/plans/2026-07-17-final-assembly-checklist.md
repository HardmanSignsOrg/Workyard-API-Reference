# Final Assembly Checklist Submissions Viewer — Implementation Plan

> **For agentic workers:** Execute task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Final Assembly board and Smart Forms submissions drill-down with a readable checklist detail view (answers, photos, signature) and date / employee / Job ID filters.

**Architecture:** Frontend-only extension of `templates/dashboard.html`. Resolve forms and load submissions via existing `/api/get/<resource>` proxy; enrich rows with per-submission detail GETs (cached). Structure-driven checklist renderer in the existing drawer.

**Tech Stack:** Flask, vanilla JS in `dashboard.html`, Workyard REST API via `WorkyardClient`.

## Global Constraints

- Read-only (no submission writes).
- Exact title match: `Final Assembly Checklist` (trim, case-insensitive) after `search=final assembly checklist`.
- Merge submissions when multiple forms match; show Form ID column only if >1 form.
- Job ID / Signs OK come from parsed `response_data` after detail enrichment.
- Reuse existing dashboard CSS / drawer / status patterns.
- No new backend endpoints unless enrichment proves too heavy (default: none).

---

## File map

| File | Role |
|------|------|
| `templates/dashboard.html` | Nav, `#submissions` section, load/enrich/render, checklist drawer, Smart Forms action |
| `README.md` | Document Final Assembly + submissions |
| `docs/superpowers/specs/2026-07-17-final-assembly-checklist-design.md` | Spec (already written) |

---

### Task 1: Submissions section shell + nav

**Files:**
- Modify: `templates/dashboard.html`

- [ ] **Step 1:** Add CSS for checklist detail (field blocks, photo thumbs, signature).

```css
  .sf-field { padding: 12px 0; border-bottom: 1px solid var(--line); }
  .sf-field .label { font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.07em;
                     color: var(--muted); margin-bottom: 4px; }
  .sf-field .value { font-size: 14px; white-space: pre-wrap; word-break: break-word; }
  .sf-photos { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; }
  .sf-photos a { display: block; width: 96px; height: 96px; border-radius: 6px; overflow: hidden;
                 border: 1px solid var(--line); background: var(--bg); }
  .sf-photos img { width: 100%; height: 100%; object-fit: cover; }
  .sf-sig img { max-width: 280px; max-height: 120px; border: 1px solid var(--line);
                border-radius: 6px; background: #fff; }
  .sf-meta { margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--line);
             color: var(--muted); font-size: 12px; }
```

- [ ] **Step 2:** Add nav button after Calendar and a `#submissions` section (toolbar + table + meta), mirroring `#browser`.

- [ ] **Step 3:** Extend `switchView` to hide/show `submissions`; add `sfState` object for forms, rows, enrichment cache, mode (`final` | `form`).

**Verify:** Dashboard loads; clicking Final Assembly shows empty section without JS errors.

---

### Task 2: Load forms + submissions list + filters + enrichment

**Files:**
- Modify: `templates/dashboard.html`

- [ ] **Step 1:** Implement helpers:

```javascript
const FINAL_TITLE = 'final assembly checklist';

function parseMaybeJson(v) {
  if (v == null) return null;
  if (typeof v === 'object') return v;
  try { return JSON.parse(v); } catch { return null; }
}

function dayStartUnix(yyyyMmDd) {
  if (!yyyyMmDd) return null;
  const [y, m, d] = yyyyMmDd.split('-').map(Number);
  return Math.floor(new Date(y, m - 1, d).getTime() / 1000);
}
function dayEndUnix(yyyyMmDd) {
  if (!yyyyMmDd) return null;
  const [y, m, d] = yyyyMmDd.split('-').map(Number);
  return Math.floor(new Date(y, m - 1, d, 23, 59, 59).getTime() / 1000);
}
```

- [ ] **Step 2:** `showFinalAssembly()` → resolve forms via `getApi('smart_forms', { search: 'final assembly checklist', all: '1' })`, exact-filter title, then `loadSubmissions({ forms, title: 'Final Assembly' })`.

- [ ] **Step 3:** `showFormSubmissions(formId, formTitle)` for Smart Forms entry (fixed single form).

- [ ] **Step 4:** `loadSubmissions` — for each form fetch `smart_forms/{id}/submissions` with `completed_at_from` / `completed_at_to` / `created_by_employee_id` when employee filter is numeric; `all=1` when Job ID filter set or Load all; merge, sort by `completed_at` desc; render table; kick off enrichment.

- [ ] **Step 5:** Enrichment — for each row `getApi(\`smart_forms/${formId}/submissions/${id}\`)`, parse `response_data`, set `job_id` from `projectName` (or first text field named like job), `signs_ok` from boolean titled like “good condition” or `question3`, photo count from file answers; re-render as each batch completes. Cap warning if >200 and Job ID filter active.

- [ ] **Step 6:** Client filters: non-numeric employee → name contains; Job ID → enriched `job_id` contains.

**Verify:** Final Assembly lists the 2 known submissions; Job ID / Signs OK fill in after enrichment.

---

### Task 3: Checklist detail drawer

**Files:**
- Modify: `templates/dashboard.html`

- [ ] **Step 1:** On row click, ensure detail loaded; call `openSubmissionDrawer(detail, formTitle)`.

- [ ] **Step 2:** Parse `form_version.structure` pages/elements; for each element render by `type`:
  - `text` / default → text value
  - `boolean` → Yes/No
  - `file` → thumbnail links from `content` URLs
  - `signaturepad` → `<img>` (data URL or http)

- [ ] **Step 3:** Footer metadata + Raw JSON toggle using existing drawer chrome (`#drawer-kv` replaced by checklist HTML container, or inject `#drawer-checklist` and hide kv when in submission mode).

**Verify:** Opening a submission shows Job ID, photos, pass/fail, signature; Raw JSON still works.

---

### Task 4: Smart Forms “View submissions” + README

**Files:**
- Modify: `templates/dashboard.html` (smart_forms `rowActions`)
- Modify: `README.md`

- [ ] **Step 1:** Add to smart_forms resource:

```javascript
rowActions: row => [{
  label: 'View submissions', cls: 'primary',
  run: () => { closeDrawer(); showFormSubmissions(row.id, row.title || `Form ${row.id}`); }
}]
```

Also improve `mapRow` for smart_forms: id, title, status, submissions_count, latest_submission_date, latest_submission_employee_name.

- [ ] **Step 2:** README bullet under Run the dashboard for Final Assembly + submissions.

**Verify:** From Smart Forms → open form 5376 → View submissions → same detail UX.

---

### Task 5: Manual smoke test

- [ ] Run `python app.py`, open http://localhost:5210
- [ ] Final Assembly → 2 rows → detail with photos/signature
- [ ] Date / employee / Job ID filters behave
- [ ] Smart Forms path works
- [ ] Refresh bypasses cache

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| Final Assembly nav + exact title | 1–2 |
| Merge multi-form | 2 |
| Table columns + filters | 2 |
| Readable checklist detail | 3 |
| Smart Forms View submissions | 4 |
| Rate-limit aware enrichment | 2 |
| README | 4 |

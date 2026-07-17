"""Workyard dashboard — local viewer/manager for the Workyard API.

Run:  python app.py
  -> http://127.0.0.1:5210
  -> http://<tailscale-ip>:5210  (same port; Tailscale up on phone + PC)

Binds 0.0.0.0 so Tailscale can reach it. Plain HTTP only
(use run-workyard.ps1 --serve-https for phone HTTPS / rapid camera).
"""

import csv
import io
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone

from dateutil.rrule import rrulestr
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request

from client import WorkyardClient, WorkyardError

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

app = Flask(__name__)
client = WorkyardClient()

ALLOWED_WRITE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}

# Short-lived GET cache so the dashboard stays inside Workyard's 60 req/min
# rate limit. Bypass with ?_refresh=1. Cleared on any successful write.
CACHE_TTL = 45
_cache = {}

def _cached_get(resource, params, fetch_all=False, refresh=False):
    key = (resource, tuple(sorted(params.items())), fetch_all)
    now = time.time()
    if not refresh and key in _cache and now - _cache[key][0] < CACHE_TTL:
        return _cache[key][1]
    if fetch_all:
        data = {'data': client.fetch_all(resource, **params), 'all': True}
    else:
        data = client.get(resource, **params)
    _cache[key] = (now, data)
    return data


@app.route('/')
def dashboard():
    try:
        org = client.org()
    except WorkyardError as exc:
        org = {'name': f'(org lookup failed: {exc.status})', 'id': client.org_id}
    return render_template('dashboard.html', org=org)


@app.route('/api/get/<path:resource>')
def api_get(resource):
    """GET passthrough for any resource under /orgs/{org_id}/.

    Extra dashboard params (stripped before the upstream call):
      all=1       fetch every page, not just one
      _refresh=1  bypass the local response cache
    """
    params = {k: v for k, v in request.args.items() if v != ''}
    fetch_all = params.pop('all', None) == '1'
    refresh = params.pop('_refresh', None) == '1'
    if fetch_all:
        params.pop('limit', None)
        params.pop('page', None)
    try:
        return jsonify(_cached_get(resource, params, fetch_all, refresh))
    except WorkyardError as exc:
        return jsonify({'error': True, 'status': exc.status, 'payload': exc.payload}), exc.status


@app.route('/api/overview')
def api_overview():
    """Aggregated org snapshot for the Overview board."""
    refresh = request.args.get('_refresh') == '1'
    week_start = datetime.now() - timedelta(days=(datetime.now().weekday()))
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start_unix = int(week_start.timestamp())
    try:
        employees = _cached_get('employees', {}, True, refresh)['data']
        projects = _cached_get('projects', {}, True, refresh)['data']
        customers = _cached_get('customers', {}, True, refresh)['data']
        tasks = _cached_get('tasks', {}, True, refresh)['data']
        time_off = _cached_get('time_off_requests', {}, True, refresh)['data']
        time_cards = _cached_get('time_cards', {}, True, refresh)['data']
    except WorkyardError as exc:
        return jsonify({'error': True, 'status': exc.status, 'payload': exc.payload}), exc.status

    now_unix = int(time.time())
    working_now, hours_by_emp, week_secs = [], {}, 0
    recent = []
    for tc in time_cards:
        start = tc.get('start_dt_unix') or 0
        end = tc.get('end_dt_unix')
        worker = (tc.get('worker') or {}).get('display_name', f"emp {tc.get('employee_id')}")
        secs = (tc.get('time_summary_v2') or {}).get('duration_secs') or 0
        if tc.get('status') == 'working' and not end:
            secs = max(secs, now_unix - start)
            working_now.append({'name': worker, 'since_unix': start,
                                'time_card_id': tc.get('id')})
        if start >= week_start_unix:
            hours_by_emp[worker] = hours_by_emp.get(worker, 0) + secs
            week_secs += secs
        recent.append({'id': tc.get('id'), 'worker': worker, 'status': tc.get('status'),
                       'start_dt_unix': start, 'end_dt_unix': end,
                       'duration_secs': secs, 'type': tc.get('type')})
    recent.sort(key=lambda r: r['start_dt_unix'] or 0, reverse=True)

    task_status = {}
    for t in tasks:
        task_status[t.get('status') or 'unknown'] = task_status.get(t.get('status') or 'unknown', 0) + 1

    return jsonify({
        'week_start_unix': week_start_unix,
        'stats': {
            'employees': len(employees),
            'projects_active': sum(1 for p in projects if not p.get('archived_dt_unix')),
            'projects_total': len(projects),
            'customers': len(customers),
            'tasks_open': sum(v for k, v in task_status.items() if k not in ('complete', 'completed')),
            'tasks_by_status': task_status,
            'time_off_pending': sum(1 for r in time_off if (r.get('status') or '').lower() == 'pending'),
            'week_hours': round(week_secs / 3600, 1),
        },
        'working_now': working_now,
        'hours_by_employee': [
            {'name': k, 'hours': round(v / 3600, 1)}
            for k, v in sorted(hours_by_emp.items(), key=lambda kv: -kv[1])
        ],
        'recent_time_cards': recent[:15],
    })


def _expand_recurrence(rec, dur_secs, win_start, win_end):
    """Expand an iCal DTSTART+RRULE string into (start, end) unix pairs
    intersecting the [win_start, win_end) window."""
    rule = rrulestr(rec)
    lo = datetime.fromtimestamp(win_start - max(dur_secs, 0), tz=timezone.utc)
    hi = datetime.fromtimestamp(win_end, tz=timezone.utc)
    # rrulestr yields naive datetimes when DTSTART has no TZID; normalize
    try:
        occurrences = rule.between(lo, hi, inc=True)
    except TypeError:
        occurrences = rule.between(lo.replace(tzinfo=None), hi.replace(tzinfo=None), inc=True)
    out = []
    for occ in occurrences:
        if occ.tzinfo is None:
            occ = occ.replace(tzinfo=timezone.utc)
        s = int(occ.timestamp())
        out.append((s, s + max(dur_secs, 0)))
    return out


def _first(row, *keys):
    for k in keys:
        if row.get(k) is not None:
            return row[k]
    return None


@app.route('/api/calendar')
def api_calendar():
    """Schedule events (tasks + time off) intersecting [start_unix, end_unix)."""
    try:
        win_start = int(request.args['start_unix'])
        win_end = int(request.args['end_unix'])
    except (KeyError, ValueError):
        return jsonify({'error': True, 'status': 400,
                        'payload': 'start_unix and end_unix are required integers'}), 400
    refresh = request.args.get('_refresh') == '1'
    try:
        tasks = _cached_get('tasks', {}, True, refresh)['data']
        time_off = _cached_get('time_off_requests', {}, True, refresh)['data']
    except WorkyardError as exc:
        return jsonify({'error': True, 'status': exc.status, 'payload': exc.payload}), exc.status

    events = []
    for t in tasks:
        start = t.get('start_dt_unix')
        due = t.get('due_dt_unix')
        dur = (due - start) if (start and due and due > start) else 0
        base = {
            'kind': 'task', 'id': t.get('id'), 'title': t.get('title') or f"task {t.get('id')}",
            'status': t.get('status'), 'recurring': bool(t.get('recurrence')),
            'assignees': [a.get('display_name') for a in (t.get('assignees') or [])],
            'project': (t.get('org_project') or {}).get('name'),
            'record': t,
        }
        if t.get('recurrence'):
            try:
                spans = _expand_recurrence(t['recurrence'], dur, win_start, win_end)
            except Exception:
                spans = [(start, (start + dur) if start else start)] if start else []
        else:
            spans = [(start, start + dur)] if start else []
        for s, e in spans:
            if s is not None and s < win_end and (e or s) >= win_start:
                events.append({**base, 'start_unix': s, 'end_unix': e or s})

    for r in time_off:
        s = _first(r, 'range_start_dt_unix', 'start_dt_unix', 'from_dt_unix')
        e = _first(r, 'range_end_dt_unix', 'end_dt_unix', 'to_dt_unix') or s
        if s is None or s >= win_end or e < win_start:
            continue
        who = (_first(r, 'employee', 'worker') or {})
        events.append({
            'kind': 'time_off', 'id': r.get('id'),
            'title': (who.get('display_name') or f"employee {r.get('employee_id')}") + ' — time off',
            'status': r.get('status'), 'recurring': False, 'assignees': [],
            'project': None, 'record': r, 'start_unix': s, 'end_unix': e,
        })

    events.sort(key=lambda ev: ev['start_unix'])
    return jsonify({'events': events})


def _flatten(row, prefix=''):
    """Flatten one level of nesting into dot keys; deeper values become JSON."""
    out = {}
    for k, v in row.items():
        key = f'{prefix}{k}'
        if isinstance(v, dict) and not prefix:
            out.update(_flatten(v, prefix=f'{k}.'))
        elif isinstance(v, (dict, list)):
            out[key] = json.dumps(v)
        else:
            out[key] = v
    return out


@app.route('/api/export/<path:resource>.csv')
def api_export(resource):
    """Export every record of a list endpoint as CSV (current filters apply)."""
    params = {k: v for k, v in request.args.items()
              if v != '' and k not in ('all', '_refresh', 'limit', 'page')}
    try:
        rows = [_flatten(r) for r in client.fetch_all(resource, **params)]
    except WorkyardError as exc:
        return jsonify({'error': True, 'status': exc.status, 'payload': exc.payload}), exc.status
    cols = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=cols, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)
    fname = re.sub(r'[^A-Za-z0-9_]+', '_', resource) + '_' + datetime.now().strftime('%Y%m%d_%H%M') + '.csv'
    return Response(buf.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename={fname}'})


@app.route('/api/spec')
def api_spec():
    """Endpoint catalog parsed from openapi.json, for the API Explorer."""
    with open(os.path.join(os.path.dirname(__file__), 'openapi.json'), encoding='utf-8') as fh:
        spec = json.load(fh)
    endpoints = []
    for path, ops in spec.get('paths', {}).items():
        for method, op in ops.items():
            if method not in ('get', 'post', 'put', 'patch', 'delete'):
                continue
            endpoints.append({
                'method': method.upper(),
                'path': path,
                'summary': op.get('summary') or op.get('description', '')[:120],
                'path_params': [p['name'] for p in op.get('parameters', [])
                                if p.get('in') == 'path' and p['name'] != 'org_id'],
                'query_params': [p['name'] for p in op.get('parameters', [])
                                 if p.get('in') == 'query'],
                'has_body': 'requestBody' in op,
            })
    endpoints.sort(key=lambda e: (e['path'], e['method']))
    return jsonify({'endpoints': endpoints})


@app.route('/api/write', methods=['POST'])
def api_write():
    """Write passthrough: {"method": "PATCH", "resource": "tasks/123", "body": {...}}."""
    req = request.get_json(force=True)
    method = (req.get('method') or '').upper()
    resource = (req.get('resource') or '').lstrip('/')
    if method not in ALLOWED_WRITE_METHODS or not resource:
        return jsonify({'error': True, 'status': 400,
                        'payload': 'method must be POST/PUT/PATCH/DELETE and resource required'}), 400
    try:
        result = client.org_request(method, resource, json=req.get('body') or None,
                                    params=req.get('params') or None)
        _cache.clear()
        return jsonify({'ok': True, 'result': result})
    except WorkyardError as exc:
        return jsonify({'error': True, 'status': exc.status, 'payload': exc.payload}), exc.status


if __name__ == '__main__':
    host = os.environ.get('WORKYARD_HOST', '0.0.0.0')
    port = int(os.environ.get('WORKYARD_PORT', '5210'))
    debug = os.environ.get('WORKYARD_DEBUG', '1').strip().lower() not in ('0', 'false', 'no')
    print(f'Workyard Ops listening on http://{host}:{port}')
    print(f'  Local:     http://127.0.0.1:{port}')
    print(f'  Tailscale: http://<this-pc-tailscale-ip>:{port}')
    # use_reloader=False avoids stacked processes fighting over :5210
    app.run(host=host, port=port, debug=debug, use_reloader=False)

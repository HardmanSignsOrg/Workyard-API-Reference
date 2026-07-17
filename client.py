"""Workyard REST API client.

Standalone client for https://api.workyard.com (spec: openapi.json in this
folder, downloaded from https://developers.workyard.com/public-api-docs.json).

Auth: Bearer API token generated in the Workyard dashboard
(Integrations -> API Token). Rate limit: 60 req/min; 429 responses carry a
Retry-After header which this client honors automatically.

Usage:
    from client import WorkyardClient
    wy = WorkyardClient()            # reads WORKYARD_API_TOKEN / WORKYARD_ORG_ID from env
    wy.employees()                   # first page
    list(wy.paginate('employees'))   # every record
"""

import os
import time

import requests


class WorkyardError(Exception):
    """Raised for any non-2xx API response (after 429 retries are exhausted)."""

    def __init__(self, status, payload, method, path):
        self.status = status
        self.payload = payload
        self.method = method
        self.path = path
        message = payload.get('message', payload) if isinstance(payload, dict) else payload
        super().__init__(f'{method} {path} -> HTTP {status}: {message}')


class WorkyardClient:
    BASE_URL = 'https://api.workyard.com'
    MAX_429_RETRIES = 5

    def __init__(self, token=None, org_id=None, timeout=30):
        self.token = token or os.environ.get('WORKYARD_API_TOKEN')
        if not self.token:
            raise ValueError('No API token: pass token= or set WORKYARD_API_TOKEN')
        self.org_id = org_id or os.environ.get('WORKYARD_ORG_ID')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.token}',
            'Accept': 'application/json',
        })

    def request(self, method, path, params=None, json=None):
        """Perform a request against an absolute API path (e.g. '/orgs').

        Returns the decoded JSON body (or None for 204). Raises WorkyardError
        on any error status. 429s are retried per the Retry-After header.
        """
        url = self.BASE_URL + path
        for attempt in range(self.MAX_429_RETRIES + 1):
            resp = self.session.request(method, url, params=params, json=json,
                                        timeout=self.timeout)
            if resp.status_code == 429 and attempt < self.MAX_429_RETRIES:
                time.sleep(float(resp.headers.get('Retry-After', 1)))
                continue
            break

        if resp.status_code == 204:
            return None
        try:
            payload = resp.json()
        except ValueError:
            payload = resp.text
        if resp.status_code >= 400:
            raise WorkyardError(resp.status_code, payload, method, path)
        return payload

    def org_request(self, method, resource, params=None, json=None):
        """Request a resource path relative to /orgs/{org_id}/."""
        if not self.org_id:
            raise ValueError('org_id not set (WORKYARD_ORG_ID)')
        return self.request(method, f'/orgs/{self.org_id}/{resource.lstrip("/")}',
                            params=params, json=json)

    def get(self, resource, **params):
        return self.org_request('GET', resource, params=params or None)

    def post(self, resource, json=None, **params):
        return self.org_request('POST', resource, params=params or None, json=json)

    def put(self, resource, json=None, **params):
        return self.org_request('PUT', resource, params=params or None, json=json)

    def patch(self, resource, json=None, **params):
        return self.org_request('PATCH', resource, params=params or None, json=json)

    def delete(self, resource, **params):
        return self.org_request('DELETE', resource, params=params or None)

    def paginate(self, resource, page_size=100, max_pages=200, **params):
        """Yield every record from a paginated list endpoint (limit/page style)."""
        page = 1
        while page <= max_pages:
            payload = self.get(resource, limit=page_size, page=page, **params)
            rows = payload.get('data', payload) if isinstance(payload, dict) else payload
            if not rows:
                return
            yield from rows
            if len(rows) < page_size:
                return
            page += 1

    def fetch_all(self, resource, **params):
        """Return every record from a paginated list endpoint as a list."""
        return list(self.paginate(resource, **params))

    def orgs(self):
        return self.request('GET', '/orgs')

    def org(self):
        return self.get('')

    def employees(self, **params):
        return self.get('employees', **params)

    def projects(self, **params):
        return self.get('projects', **params)

    def customers(self, **params):
        return self.get('customers', **params)

    def time_cards(self, **params):
        return self.get('time_cards', **params)

    def tasks(self, **params):
        return self.get('tasks', **params)

    def tags(self, **params):
        return self.get('tags', **params)

    def geofences(self, **params):
        return self.get('geofences', **params)

    def time_off_requests(self, **params):
        return self.get('time_off_requests', **params)

    def smart_forms(self, **params):
        return self.get('smart_forms', **params)

    def cost_codes(self, project_id, **params):
        return self.get(f'projects/{project_id}/cost_codes', **params)

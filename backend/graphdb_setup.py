"""
Configure GraphDB repository ruleset (enable OWL2-RL) and trigger reindex.
Reads `backend/graphdb_config.json` for connection info.
"""
import json
import os
import sys
from urllib.parse import urljoin

BASE = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(BASE, 'graphdb_config.json')

if not os.path.exists(CFG_PATH):
    print('graphdb_config.json not found at', CFG_PATH)
    sys.exit(2)

with open(CFG_PATH, 'r', encoding='utf8') as fh:
    cfg = json.load(fh)

g = cfg.get('graphdb') or cfg
endpoint = g.get('endpoint') or g.get('graphdb_url') or g.get('url')
repo = g.get('repository')
use_auth = g.get('use_auth', False)
username = g.get('username') or g.get('user') or ''
password = g.get('password') or ''

if not endpoint or not repo:
    print('Missing endpoint or repository in config:', CFG_PATH)
    sys.exit(3)

print('GraphDB endpoint:', endpoint)
print('Repository:', repo)

import requests

session = requests.Session()
if use_auth and username:
    session.auth = (username, password)

# Try to get current settings
settings_url = endpoint.rstrip('/') + f"/rest/repositories/{repo}/settings"
print('GET', settings_url)
try:
    r = session.get(settings_url, headers={'Accept':'application/json'}, timeout=10)
    print('GET status', r.status_code)
    print(r.text[:2000])
except Exception as e:
    print('GET settings failed:', e)

# Attempt to set ruleset to owl2-rl
payload = { 'ruleset': 'owl2-rl' }
headers = {'Content-Type':'application/json'}
print('PATCH', settings_url, '->', payload)
try:
    rp = session.patch(settings_url, json=payload, headers=headers, timeout=10)
    print('PATCH status', rp.status_code)
    print(rp.text[:2000])
except Exception as e:
    print('PATCH failed:', e)

# If PATCH returned 405 or not allowed, try PUT
if 'rp' in locals() and rp.status_code not in (200,204):
    print('PATCH did not succeed, trying PUT')
    try:
        rput = session.put(settings_url, json=payload, headers=headers, timeout=10)
        print('PUT status', rput.status_code)
        print(rput.text[:2000])
    except Exception as e:
        print('PUT failed:', e)

# Try listing repositories to detect API
repos_url = endpoint.rstrip('/') + '/rest/repositories'
try:
    rlist = session.get(repos_url, headers={'Accept':'application/json'}, timeout=10)
    print('List repos status', rlist.status_code)
    print(rlist.text[:2000])
except Exception as e:
    print('List repos failed:', e)

# Trigger reindex
reindex_url = endpoint.rstrip('/') + f"/rest/repositories/{repo}/reindex"
print('POST reindex', reindex_url)
try:
    rx = session.post(reindex_url, timeout=10)
    print('Reindex status', rx.status_code)
    print(rx.text[:2000])
except Exception as e:
    print('Reindex failed:', e)

print('Done')

# If repository is inactive, attempt to activate it via common admin endpoints
try:
    # Check repository list to get state
    rep_info = rlist.json()[0] if 'rlist' in locals() and rlist.status_code==200 else None
    state = rep_info.get('state') if rep_info else None
    print('Repository reported state:', state)
    if state and state.upper() != 'ACTIVE':
        print('Attempting to activate repository...')
        attempts = [
            endpoint.rstrip('/') + f"/rest/repositories/{repo}/start",
            endpoint.rstrip('/') + f"/rest/repositories/{repo}/activate",
            endpoint.rstrip('/') + f"/rest/repositories/{repo}/actions/start",
            endpoint.rstrip('/') + f"/rest/repositories/{repo}/state"
        ]
        for url in attempts:
            try:
                print('TRY POST', url)
                ract = session.post(url, timeout=10)
                print('POST', url, '->', ract.status_code)
                print(ract.text[:1000])
            except Exception as e:
                print('POST failed for', url, e)
        # As a last resort try PUT state=ACTIVE
        try:
            url = endpoint.rstrip('/') + f"/rest/repositories/{repo}/state"
            print('TRY PUT', url)
            rput = session.put(url, data='ACTIVE', headers={'Content-Type':'text/plain'}, timeout=10)
            print('PUT state ->', rput.status_code)
            print(rput.text[:1000])
        except Exception as e:
            print('PUT state failed:', e)
except Exception as e:
    print('Activation attempt error:', e)

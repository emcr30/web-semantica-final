"""Script sencillo para subir un archivo TTL a un repositorio de GraphDB.
Uso:
  python backend/graphdb_upload.py --config backend/graphdb_config.json --file Ontologia/legal_working.ttl

El script hace POST a: {graphdb_url}/repositories/{repo}/statements
Autenticación básica si se provee usuario/clave.
"""
import requests
import argparse
import json
import os


def load_config(path):
    with open(path,'r',encoding='utf8') as f:
        return json.load(f)


def upload_ttl(config, ttl_path):
    url = config.get('graphdb_url')
    repo = config.get('repository')
    if not url or not repo:
        raise ValueError('graphdb_url and repository must be set in config')
    endpoint = f"{url.rstrip('/')}/repositories/{repo}/statements"
    headers = {'Content-Type':'text/turtle'}
    auth = None
    if config.get('username'):
        auth = (config.get('username'), config.get('password',''))
    with open(ttl_path, 'rb') as fh:
        data = fh.read()
    try:
        r = requests.post(endpoint, data=data, headers=headers, auth=auth, timeout=60)
        ok = r.status_code >=200 and r.status_code < 300
        result = {
            'ok': ok,
            'status_code': r.status_code,
            'text': r.text
        }
        if not ok:
            # include reason
            result['error'] = f'HTTP {r.status_code}: {r.text[:200]}'
        else:
            print('Upload OK, status code', r.status_code)
        return result
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config','-c', default='backend/graphdb_config.json')
    parser.add_argument('--file','-f', required=True)
    args = parser.parse_args()
    cfg_path = args.config
    if not os.path.exists(cfg_path):
        print('Config not found:', cfg_path)
        return
    cfg = load_config(cfg_path)
    out = upload_ttl(cfg, args.file)
    print(out[:200])

if __name__=='__main__':
    main()

import requests

# Placeholder module to fetch Peruvian laws from a public API.
# Replace endpoint and payload with the real API of datos.gob.pe or similar.

API_BASE = 'https://www.datos.gob.pe/api/3/action'


def fetch_laws_from_api(api_key: str | None, query: str = ''):
    """Fetch a list of laws from the Peruvian open data API.
    This is a template: adapt `resource_search` to the real endpoint and parameters.

    Returns a list of dict {id, title, text, jurisdiccion}
    """
    # Example: dataset search (this is just illustrative — update as needed)
    params = {'q': query, 'rows': 10}
    try:
        r = requests.get(f'{API_BASE}/package_search', params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        results = []
        for res in data.get('result', {}).get('results', [])[:10]:
            title = res.get('title')
            # No standard text field — you must fetch resource details separately
            results.append({'id': res.get('id'), 'title': title, 'text': res.get('notes',''), 'jurisdiccion':'Peru'})
        return results
    except Exception:
        # In case of failure, return empty list — this keeps ingestion robust
        return []

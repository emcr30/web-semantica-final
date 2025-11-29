import csv
import requests
from io import StringIO
from rdflib import Graph
from backend import rdf_builder
from bs4 import BeautifulSoup
from pdfminer.high_level import extract_text as extract_text_from_pdf
import os
import json


def ingest_csv_url_into_graph(g: Graph, csv_url: str, limit=50):
    """Descarga un CSV público que contenga metadatos de normas y crea individuos Ley en el grafo.
    Se busca columnas típicas: 'titulo'/'title', 'enlace'/'link'/'url', 'texto'/'notes'.
    """
    # Support local file paths (absolute or relative) as well as HTTP URLs
    if csv_url.startswith('http://') or csv_url.startswith('https://'):
        r = requests.get(csv_url, timeout=30)
        r.raise_for_status()
        text = r.content.decode('utf-8', errors='replace')
        reader = csv.DictReader(StringIO(text))
    else:
        # treat csv_url as a local file path
        path = csv_url
        if csv_url.startswith('file://'):
            path = csv_url[7:]
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            text = fh.read()
        reader = csv.DictReader(StringIO(text))
    created = []
    # Normalize header keys to lowercase for flexible access
    rows = list(reader)
    for i, row in enumerate(rows):
        if i>=limit: break
        # attempt to find common Spanish/English column names
        def get_any(r, keys):
            for k in keys:
                if k in r and r[k] is not None:
                    return r[k]
            return ''

        # try original keys, then lowercase variants
        lowered = { (k.lower() if isinstance(k,str) else k): v for k,v in row.items() }
        title = get_any(lowered, ['sumilla','titulo','title','nombre','name'])
        notes = get_any(lowered, ['texto','notes','resumen','descripcion','description'])
        link = get_any(lowered, ['link','enlace','url'])
        numero = get_any(lowered, ['numero','num','nro','op'])
        # If text is empty but there's a link, try to fetch HTML and extract text (basic)
        text_content = notes
        if not text_content and link:
            text_content = fetch_text_from_link(link)
        # determine id: prefer OP or NUMERO or fallback to title slug
        law_id = get_any(lowered, ['op','numero','id','identificador']) or (title[:40].replace(' ','_'))
        rdf_builder.create_law(g, law_id, title, text_content, jurisdiction='Peru')
        created.append(law_id)
    # After ingest, persist working TTL
    upload_result = None
    try:
        base = os.path.dirname(os.path.dirname(__file__))
        out = os.path.join(base, 'Ontologia', 'legal_working.ttl')
        g.serialize(destination=out, format='turtle')
        # attempt upload to GraphDB if config exists
        cfg_path = os.path.join(base, 'backend', 'graphdb_config.json')
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path,'r',encoding='utf8') as fh:
                    cfg = json.load(fh)
                from backend.graphdb_upload import upload_ttl
                upload_result = upload_ttl(cfg, out)
            except Exception as e:
                upload_result = { 'ok': False, 'error': str(e) }
    except Exception as e:
        # persist failure shouldn't break ingestion return
        upload_result = { 'ok': False, 'error': str(e) }
    return { 'created': created, 'upload': upload_result }


def fetch_text_from_link(link: str) -> str:
    """Best-effort text extraction from a link. Handles HTML and PDF (text-based)."""
    try:
        headers = {'User-Agent': 'LegalOntoSystem/1.0 (+https://example.org)'}
        r = requests.get(link, timeout=25, headers=headers, allow_redirects=True)
        r.raise_for_status()
        ctype = r.headers.get('content-type','').lower()
        if 'application/pdf' in ctype or link.lower().endswith('.pdf'):
            # Save to temp file and extract with pdfminer
            from tempfile import NamedTemporaryFile
            with NamedTemporaryFile(delete=False, suffix='.pdf') as tf:
                tf.write(r.content)
                tmpname = tf.name
            try:
                text = extract_text_from_pdf(tmpname)
                return text[:20000]
            except Exception:
                return ''
            finally:
                try:
                    os.remove(tmpname)
                except Exception:
                    pass
        else:
            # parse HTML
            try:
                soup = BeautifulSoup(r.text, 'html.parser')
                # prefer article/body
                article = soup.find('article')
                if article:
                    txt = article.get_text(separator=' ', strip=True)
                else:
                    body = soup.find('body')
                    txt = body.get_text(separator=' ', strip=True) if body else soup.get_text(separator=' ', strip=True)
                return txt[:20000]
            except Exception:
                return r.text[:20000]
    except Exception:
        return ''


if __name__=='__main__':
    import sys, os
    BASE = os.path.dirname(os.path.dirname(__file__))
    g = Graph()
    # try loading existing ontology
    try:
        g.parse(os.path.join(BASE,'Ontologia','legalontosystem_peru.ttl'), format='turtle')
    except Exception:
        pass
    if len(sys.argv)<2:
        print('Usage: python backend/dataset_ingest.py <csv_url>')
        sys.exit(1)
    csv_url = sys.argv[1]
    created = ingest_csv_url_into_graph(g, csv_url, limit=200)
    out = os.path.join(BASE,'Ontologia','legal_working.ttl')
    g.serialize(destination=out, format='turtle')
    print('Created', len(created), 'laws; saved to', out)

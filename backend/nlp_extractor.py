"""NLP module for extracting entities and keywords from legal texts using spaCy.

This module now handles very large texts by chunking them into smaller pieces
so spaCy's `nlp.max_length` is not exceeded. It merges entities across chunks
and deduplicates results.
"""
import spacy
import re
from .nlp_chunker import chunk_text

# Try to load Spanish model; fallback to blank if not available
try:
    nlp = spacy.load('es_core_news_sm')
except OSError:
    print("Warning: es_core_news_sm model not found. Install with: python -m spacy download es_core_news_sm")
    nlp = spacy.blank('es')

# sensible defaults: chunk to 100k chars with 2k overlap
DEFAULT_MAX_LEN = 100000
DEFAULT_OVERLAP = 2000

ARTICLE_RE = re.compile(r'(?:artículo|art\.?|art)\s+(\d+(?:[bis|ter|quater|quinquies]*)?)', re.IGNORECASE)
LAW_NUMBER_RE = re.compile(r'(?:ley|decreto|norma)\s+(?:n\.?|n°|nº)\s*(\d+(?:\.\d+)*)', re.IGNORECASE)
KEYWORD_PATTERNS = [
    r'\b(?:delito|crimen|fraude|robo|homicidio|violencia)\b',
    r'\b(?:contrato|acuerdo|obligación|responsabilidad)\b',
    r'\b(?:derecho|deber|libertad|propiedad)\b',
    r'\b(?:pena|sanción|multa|prisión)\b',
]

# Patterns for case metadata
TITLE_RE = re.compile(r'\b(CASACI(?:Ó|O)N|Casaci(?:ó|o)n)\s*(?:N\.?\s*\u00BA|N\.?\s*°|N\.?\s*)?\s*([\d\-/]+)', re.IGNORECASE)
CHAMBER_RE = re.compile(r'\b(SALA\s+[^\n\r,]{5,100})', re.IGNORECASE)
DEPARTMENT_RE = re.compile(r'\b([A-Z][a-z]+)\b')
ORDINAL_MAP = {
    'primera': 1, 'primero': 1,
    'segunda': 2, 'segundo': 2,
    'tercera': 3, 'tercero': 3,
    'cuarta': 4, 'cuarto': 4,
    'quinta': 5, 'quinto': 5,
}
CRIME_RE = re.compile(r'\bDelit[eo]s?\s+de\s+([\w\s]+?)(?:[\.,\n]|$)', re.IGNORECASE)


def extract_case_metadata(text):
    """Extract case-specific metadata from full case text.

    Returns dict with keys: title, department, chamber, chamber_number, crime_labels
    """
    out = {'title': None, 'department': None, 'chamber': None, 'chamber_number': None, 'crime_labels': []}
    if not text:
        return out

    # Title detection: look for CASACIÓN N.° 412-2022 or similar
    m = TITLE_RE.search(text)
    if m:
        kind = m.group(1)
        num = m.group(2)
        out['title'] = f"{kind} N.° {num}"

    # Chamber detection: e.g., 'SALA PENAL PERMANENTE DE JUSTICIA'
    m = CHAMBER_RE.search(text)
    if m:
        chamber = m.group(1).strip()
        out['chamber'] = ' '.join(chamber.split())
        # try to find ordinal word near chamber
        # look in a short window after chamber for words like 'primera', 'segunda'
        window = text[m.end():m.end()+200].lower()
        for w, n in ORDINAL_MAP.items():
            if w in window:
                out['chamber_number'] = n
                break

    # Department detection via spaCy GPE entities (best-effort)
    try:
        doc = nlp(text[:4000])  # examine beginning of document
        for ent in doc.ents:
            if ent.label_ == 'GPE' and len(ent.text) <= 30:
                # simple heuristic: choose first proper noun-looking GPE as department
                out['department'] = ent.text.strip()
                break
    except Exception:
        pass

    # Crime labels
    for cm in CRIME_RE.findall(text):
        lab = cm.strip()
        if lab and lab.lower() not in [x.lower() for x in out['crime_labels']]:
            out['crime_labels'].append(lab)

    return out



def _process_chunk(chunk_text_content):
    """Process a single chunk with spaCy and return entities list."""
    try:
        doc = nlp(chunk_text_content)
    except Exception as e:
        # If spaCy still fails on a chunk, return empty list but don't stop whole pipeline
        return []
    ents = []
    for ent in doc.ents:
        if ent.label_ in ['PERSON', 'ORG', 'GPE', 'MISC']:
            ents.append({'text': ent.text.strip(), 'label': ent.label_})
    return ents


def extract_entities(text, max_len=DEFAULT_MAX_LEN, overlap=DEFAULT_OVERLAP):
    """
    Extract entities, articles, laws, and keywords from legal text.

    For very long `text`, it will chunk and process each piece to avoid
    spaCy's `nlp.max_length` errors. Returns dict with:
    - articles: list of article numbers mentioned
    - laws: list of law numbers mentioned
    - entities: spaCy named entities (deduplicated)
    - keywords: list of important legal terms
    """
    result = {'articles': [], 'laws': [], 'entities': [], 'keywords': []}

    if not text:
        return result

    # Extract article references and laws from whole text using regex (fast)
    article_matches = ARTICLE_RE.findall(text)
    result['articles'] = list(dict.fromkeys(article_matches))  # preserve order, unique

    law_matches = LAW_NUMBER_RE.findall(text)
    result['laws'] = list(dict.fromkeys(law_matches))

    # Extract keywords from whole text
    kws = []
    for pattern in KEYWORD_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        kws.extend(matches)
    result['keywords'] = list(dict.fromkeys(kws))

    # Now process text in chunks for spaCy entities
    seen = set()
    entities = []
    for start_idx, chunk in chunk_text(text, max_len=max_len, overlap=overlap):
        ents = _process_chunk(chunk)
        for e in ents:
            key = (e['text'].lower(), e['label'])
            if key not in seen:
                seen.add(key)
                entities.append(e)

    result['entities'] = entities
    return result

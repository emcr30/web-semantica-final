import spacy
import re

# Cargar modelo español (descargar con `python -m spacy download es_core_news_sm`)
try:
    nlp = spacy.load('es_core_news_sm')
except Exception:
    nlp = None

ARTICLE_RE = re.compile(r"(?:Artículo|Art\.?)\s*(\d+[A-Za-z0-9\-]*)", re.IGNORECASE)


def process_law_text(text: str):
    """Procesa el texto de una ley y extrae título, artículos y entidades.
    Retorna: { title, articles: [{number, text}], entities: [{text, label}] }
    """
    doc = nlp(text) if nlp else None
    title = None
    entities = []
    if doc:
        # heurística: título = primeras 200 chars or first line
        title = text.strip().split('\n',1)[0][:200]
        for ent in doc.ents:
            entities.append({'text': ent.text, 'label': ent.label_})
    else:
        title = text.strip().split('\n',1)[0][:200]

    # Extraer artículos por regex como fallback
    articles = []
    for m in ARTICLE_RE.finditer(text):
        num = m.group(1)
        # get context after match
        start = m.end()
        snippet = text[start:start+500]
        # split by next 'Artículo' to approximate full article text
        next_m = ARTICLE_RE.search(snippet)
        article_text = snippet if not next_m else snippet[:next_m.start()]
        articles.append({'number':num.strip(), 'text': article_text.strip()})

    return {'title': title, 'articles': articles, 'entities': entities}

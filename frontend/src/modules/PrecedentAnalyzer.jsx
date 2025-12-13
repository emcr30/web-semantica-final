import React, {useState, useEffect} from 'react'
import axios from 'axios'
import { Card, Form, Button, Badge, Spinner, Row, Col, ListGroup, Alert } from 'react-bootstrap'

export default function PrecedentAnalyzer({API_BASE}){
  const [selectedLaw, setSelectedLaw] = useState('')
  const [laws, setLaws] = useState([])
  const [precedents, setPrecedents] = useState(null)
  const [loading, setLoading] = useState(false)
  const [overview, setOverview] = useState(null)
  const [loadingOverview, setLoadingOverview] = useState(false)

  useEffect(() => {
    loadLawsList()
    const handler = (e) => {
      if (selectedLaw) findPrecedents()
    }
    window.addEventListener('case:uploaded', handler)
    return () => window.removeEventListener('case:uploaded', handler)
  }, [])

  async function loadLawsList(){
    try{
      const sparql = `
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX lo: <http://legalontosystem.pe/ontology#>
SELECT ?res ?label ?titulo WHERE {
  { ?res a lo:Ley } UNION { ?res a lo:Articulo } UNION { ?res a lo:Documento } .
  OPTIONAL { ?res rdfs:label ?label }
  OPTIONAL { ?res lo:titulo ?titulo }
} LIMIT 100
      `
      try{
        const res = await axios.post(`${API_BASE}/sparql`, { query: sparql })
        const lawsList = (res.data.results || []).map(r => ({
          uri: r.res || r['?res'],
          title: r.label || r['?label'] || r.titulo || r['?titulo']
        }))
        const filtered = lawsList.filter(l => {
          const t = (l.title || '').toString().trim()
          if(!t) return false
          const tl = t.toLowerCase()
          if(tl === 'none' || tl === 'null') return false
          if(tl.endsWith('.pdf')) return false
          if((l.uri||'').startsWith('http://legalontosystem.pe/resource/')) return false
          return true
        })
        setLaws(filtered)
      }catch(e){
        const r2 = await axios.get(`${API_BASE}/list_resources`)
        const list = (r2.data.results || []).filter(i => !i.is_part).map(i=>({ uri: i.uri, title: i.title }))
        const filtered2 = list.filter(l => {
          const t = (l.title || '').toString().trim()
          if(!t) return false
          const tl = t.toLowerCase()
          if(tl === 'none' || tl === 'null') return false
          if(tl.endsWith('.pdf')) return false
          if((l.uri||'').startsWith('http://legalontosystem.pe/resource/')) return false
          return true
        })
        setLaws(filtered2)
      }
    }catch(err){
      console.error('Error loading laws:', err)
    }
  }

  async function findPrecedents(){
    if(!selectedLaw){
      alert('Por favor selecciona una ley')
      return
    }

    setLoading(true)
    try{
      const res = await axios.get(`${API_BASE}/precedents_for_article`, {
        params: {
          uri: selectedLaw,
          limit: 50
        }
      })
      let items = res.data.results || []
      const enriched = []
      const maxEnrich = 10
      for(let i=0;i<items.length;i++){
        const it = items[i]
        const out = { ...it }
        if(i < maxEnrich){
          try{
            const er = await axios.get(`${API_BASE}/entity`, { params: { uri: it.case } })
            const props = er.data.properties || []
            props.forEach(p => {
              if(p.p.endsWith('#label') || p.p.endsWith('/rdfs/label')) out.title = out.title || p.o
              if(p.p.endsWith('jurisdiccionCaso')) out.jurisdiction = out.jurisdiction || p.o
              if(p.p.endsWith('fechaSentencia')) out.date = out.date || p.o
              if(p.p.endsWith('delitoLiteral')) out.crime = out.crime || p.o
              if(p.p.endsWith('archivoFilename') || (p.o && p.o.toLowerCase && p.o.toLowerCase().endsWith('.pdf'))){
                const fname = p.o
                try{
                  out.pdf = `${API_BASE.replace(/\/$/, '')}/files/${encodeURIComponent(fname)}`
                }catch(e){ }
              }
            })
          }catch(e){ }
        }
        enriched.push(out)
      }
      setPrecedents(enriched)
    }catch(err){
      console.error(err)
      alert('Error al buscar precedentes: ' + err.message)
    }finally{
      setLoading(false)
    }
  }

  async function loadOverview(){
    setLoadingOverview(true)
    try{
      const res = await axios.get(`${API_BASE}/cases_overview`, { params: { limit: 1000 } })
      setOverview(res.data.results || [])
    }catch(err){
      console.error('cases_overview failed, trying SPARQL fallback:', err)
      try{
          const q = `
PREFIX lo: <http://legalontosystem.pe/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?case ?label ?date ?jur ?crime ?pdf ?art ?artLabel ?artNum ?law1 ?law1Label ?law2 ?law2Label
WHERE {
        { ?case a lo:Caso } UNION { ?case a lo:Documento } .
  OPTIONAL { ?case rdfs:label ?label }
  OPTIONAL { ?case lo:fechaSentencia ?date }
  OPTIONAL { ?case lo:jurisdiccionCaso ?jur }
  OPTIONAL { ?case lo:delitoLiteral ?crime }
  OPTIONAL { ?case lo:archivoFilename ?pdf }
  OPTIONAL {
    ?case lo:mencionaArticulo ?art .
    OPTIONAL { ?art rdfs:label ?artLabel }
    OPTIONAL { ?art lo:articleNumber ?artNum }
    OPTIONAL { ?law1 lo:tieneArticulo ?art . OPTIONAL { ?law1 rdfs:label ?law1Label } }
    OPTIONAL { ?law2 lo:hasArticle ?art . OPTIONAL { ?law2 rdfs:label ?law2Label } }
  }
}
LIMIT 2000`;
        const sr = await axios.post(`${API_BASE}/sparql`, { query: q })
        const rows = sr.data?.results || []
        // Group by case
        const map = {}
        rows.forEach(r => {
          const c = r.case || r['?case']
          if(!c) return
          const it = map[c] || { case: c, label: r.label || r['?label'], date: r.date || r['?date'], jurisdiction: r.jur || r['?jur'], crime: r.crime || r['?crime'], pdf: r.pdf || r['?pdf'], articles: [] }
          // article
          const art = r.art || r['?art']
          if(art){
            const existing = it.articles.find(a => a.uri === art)
            const laws = []
            if(r.law1 || r['?law1']) laws.push({ uri: r.law1 || r['?law1'], label: r.law1Label || r['?law1Label'] })
            if(r.law2 || r['?law2']) laws.push({ uri: r.law2 || r['?law2'], label: r.law2Label || r['?law2Label'] })
            if(existing){
              existing.laws = [...existing.laws, ...laws]
            } else {
              it.articles.push({ uri: art, label: r.artLabel || r['?artLabel'], number: r.artNum || r['?artNum'], laws })
            }
          }
          map[c] = it
        })
        setOverview(Object.values(map))
      }catch(fbErr){
        console.error('SPARQL fallback failed:', fbErr)
        alert('Error al cargar el resumen de casos: ' + (fbErr.response?.data?.error || fbErr.message))
      }
    }finally{
      setLoadingOverview(false)
    }
  }

  return (
    <div className="fade-in">
      <Card className="mb-4">
        <Card.Header>
          <Card.Title className="mb-0">Análisis de Precedentes Jurisprudenciales</Card.Title>
          <small className="text-white-50">Localiza casos relacionados y precedentes según la norma legal</small>
        </Card.Header>
        <Card.Body>
          <Form.Group className="mb-3">
            <Form.Label className="fw-bold">Selecciona una Ley o Artículo</Form.Label>
            <Form.Select
              value={selectedLaw}
              onChange={e => setSelectedLaw(e.target.value)}
              className="form-control"
            >
              <option value="">-- Elige una norma --</option>
              {laws.map(law => (
                <option key={law.uri} value={law.uri}>
                  {law.title || law.uri}
                </option>
              ))}
            </Form.Select>
          </Form.Group>

          <div className="d-flex gap-2">
            <Button
              variant="primary"
              onClick={findPrecedents}
              disabled={loading || !selectedLaw}
            >
              {loading ? (
                <>
                  <Spinner size="sm" animation="border" className="me-2" />
                  Buscando...
                </>
              ) : (
                'Buscar Precedentes'
              )}
            </Button>
            <Button
              variant="outline-secondary"
              onClick={loadOverview}
              disabled={loadingOverview}
            >
              {loadingOverview ? (
                <>
                  <Spinner size="sm" animation="border" className="me-2" />
                  Cargando todos los casos...
                </>
              ) : (
                'Ver todos los casos y vínculos'
              )}
            </Button>
          </div>
        </Card.Body>
      </Card>

      {precedents && precedents.length > 0 && (
        <Card className="mb-4">
          <Card.Header>
            <Card.Title className="mb-0">
              Precedentes Encontrados
              <Badge bg="info" className="ms-2">{precedents.length}</Badge>
            </Card.Title>
          </Card.Header>
          <Card.Body>
            <ListGroup variant="flush">
              {precedents.map((prec, i) => (
                <ListGroup.Item key={i} className="mb-3 p-3">
                  <Row>
                    <Col md="auto" className="mb-3 mb-md-0">
                      <div className="text-center">
                        <h5 className="text-primary mb-1">#{i+1}</h5>
                        {prec.score && (
                          <Badge bg="success" className="text-xs">
                            {(prec.score * 100).toFixed(0)}% match
                          </Badge>
                        )}
                      </div>
                    </Col>
                    <Col>
                      <h6 className="mb-2 text-dark">{prec.title || prec.case_id || 'Caso sin título'}</h6>
                      {prec.crime && (
                        <Badge bg="danger" className="me-2 mb-2">{prec.crime}</Badge>
                      )}
                      {prec.jurisdiction && (
                        <Badge bg="warning" className="me-2 mb-2">📍 {prec.jurisdiction}</Badge>
                      )}
                      {prec.date && (
                        <Badge bg="secondary" className="mb-2">📅 {prec.date}</Badge>
                      )}
                      {prec.description && (
                        <p className="mt-2 mb-2 text-muted small">{prec.description}</p>
                      )}
                      {prec.pdf && (
                        <div className="mt-3">
                          <a href={prec.pdf} target="_blank" rel="noreferrer" className="btn btn-sm btn-outline-primary">
                            Ver PDF Completo
                          </a>
                        </div>
                      )}
                    </Col>
                  </Row>
                </ListGroup.Item>
              ))}
            </ListGroup>
          </Card.Body>
        </Card>
      )}

      {precedents && precedents.length === 0 && (
        <Alert variant="info">
          <Alert.Heading>Sin resultados</Alert.Heading>
          <p className="mb-0">No se encontraron precedentes para la norma seleccionada. Intenta con otra ley o artículo.</p>
        </Alert>
      )}

      {overview && (
        <Card className="mb-4">
          <Card.Header>
            <Card.Title className="mb-0">Todos los casos y vínculos</Card.Title>
          </Card.Header>
          <Card.Body>
            <ListGroup variant="flush">
              {overview.map((item, idx) => (
                <ListGroup.Item key={idx} className="mb-3">
                  <div className="mb-1 fw-semibold text-primary">{item.label || item.case}</div>
                  <div className="small text-muted mb-2">
                    {item.date && <span className="me-3">📅 {item.date}</span>}
                    {item.jurisdiction && <span className="me-3">📍 {item.jurisdiction}</span>}
                    {item.crime && <span className="me-3">⚖️ {item.crime}</span>}
                  </div>
                  {(item.articles || []).length > 0 ? (
                    <div>
                      {(item.articles || []).map((a, i) => (
                        <div key={i} className="mb-1">
                          <Badge bg="info" className="me-2">Artículo {a.number || ''}</Badge>
                          <span className="me-2">{a.label || a.uri}</span>
                          {(a.laws || []).map((lw, j) => (
                            <Badge key={j} bg="secondary" className="me-1">{lw.label || lw.uri}</Badge>
                          ))}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-muted small">Sin vínculos a artículos</div>
                  )}
                </ListGroup.Item>
              ))}
            </ListGroup>
          </Card.Body>
        </Card>
      )}
    </div>
  )
}

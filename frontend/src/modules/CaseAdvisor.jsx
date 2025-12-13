import React, {useState} from 'react'
import axios from 'axios'
import { Card, Form, Button, Row, Col, Badge, Alert, Spinner, ListGroup } from 'react-bootstrap'

export default function CaseAdvisor({API_BASE}){
  const [caseDescription, setCaseDescription] = useState('')
  const [recommendations, setRecommendations] = useState(null)
  const [loading, setLoading] = useState(false)
  const [extractedEntities, setExtractedEntities] = useState(null)

  // Basic Spanish normalization and semantic keyword expansion
  const normalize = (s) => (s || '')
    .toLowerCase()
    .normalize('NFD').replace(/\p{Diacritic}/gu, '')
    .replace(/[^a-z0-9\sáéíóúñ]/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  // Escape strings for safe SPARQL double-quoted literals
  const sparqlLiteral = (s) => (s || '')
    .replace(/\\/g, '\\\\')
    .replace(/"/g, '\\"')
    .replace(/\n/g, ' ')
    .trim()

  // Normalize URIs to canonical ELI form for deduplication
  const normalizeUri = (u) => {
    if (!u) return u
    let x = u.trim()
    // strip trailing slash
    x = x.replace(/\/$/, '')
    // map known hosts to canonical leyes.peru
    x = x.replace(/^https?:\/\/[^/]+\/eli\//, 'https://leyes.peru/eli/')
    return x
  }

  const expandKeywords = (desc, kws) => {
    const base = new Set((kws || []).map(k => normalize(k)))
    const nd = normalize(desc)
    const add = (t) => { if (t && t.length >= 3) base.add(t) }

    // Heuristic cues from description
    if (/muerte inmediata|murio|fallecio|le caus[oó] la muerte/.test(nd)) {
      add('homicidio'); add('asesinato'); add('muerte')
    }
    if (/cuchillo|arma blanca|apu[nñ]al/.test(nd)) { add('arma blanca'); add('cuchillo') }
    if (/pelea|ri[ñn]a|discusion/.test(nd)) { add('riña'); add('pelea'); add('discusion') }
    if (/no existio planificacion previa|sin premeditacion|no hubo planificacion/.test(nd)) {
      add('sin premeditacion'); add('homicidio simple'); add('dolo'); add('culposo')
    }

    // Synonym expansion map (legal spanish)
    const syn = {
      'asesinato': ['homicidio', 'dar muerte', 'matar'],
      'homicidio': ['asesinato', 'muerte', 'dar muerte'],
      'muerte': ['fallecimiento', 'deceso'],
      'cuchillo': ['arma blanca', 'navaja'],
      'pelea': ['riña', 'altercado', 'discusion'],
      'sin premeditacion': ['no premeditado', 'no planificado'],
      'dolo': ['intencional'],
      'culposo': ['negligente']
    }
    // Seed with a few high-signal terms from description even if NLP missed them
    if (nd.includes('muerte inmediata')) { add('homicidio') }

    // Expand synonyms
    Array.from(base).forEach(t => {
      const s = syn[t]
      if (s) s.forEach(add)
    })
    return Array.from(base)
  }

  async function analyzeCase(){
    if(!caseDescription.trim()){
      alert('Por favor ingresa la descripción del caso')
      return
    }

    setLoading(true)
    try{
      // Step 1: Extract entities using spaCy backend
      const nlpRes = await axios.post(`${API_BASE}/nlp_extract`, {
        text: caseDescription
      })
      setExtractedEntities(nlpRes.data)

      // Step 2: Semantic advisor via backend (no SPARQL)
      try {
        const adv = await axios.post(`${API_BASE}/advise_case`, { text: caseDescription })
        const items = Array.isArray(adv.data?.applicable) ? adv.data.applicable : []
        if (items.length > 0) {
          setRecommendations({
            entities: nlpRes.data,
            applicableLaws: items.map(it => ({ law: it.uri, title: it.title })),
            reasoning: `Se detectaron indicios del tipo penal y se recuperaron artículos vinculados al caso a través de menciones explícitas y taxonomía del delito.`
          })
          setLoading(false)
          return
        }
      } catch (e) {
        // proceed to keyword search fallback
      }

      // Step 3: Search for applicable laws based on expanded keywords (fallback)
      const articles = nlpRes.data.articles || []
      const keywords = expandKeywords(caseDescription, nlpRes.data.keywords || [])
      
      let recs = {
        entities: nlpRes.data,
        applicableLaws: [],
        reasoning: ''
      }

      // Query per keyword via backend text search to avoid SPARQL parser issues; aggregate results
      const kwSet = Array.from(new Set(keywords.map(k => (k || '').toString().trim()).filter(k => k.length >= 3)))
      const topKw = kwSet.slice(0, 8)
      const aggregate = new Map() // normalized uri -> title
      for (const kw of topKw) {
        try {
          const resp = await axios.post(`${API_BASE}/search_text`, { keywords: [kw], limit: 40 })
          const items = Array.isArray(resp.data?.results) ? resp.data.results : []
          items.forEach(it => {
            const uri = normalizeUri(it.res)
            const title = it.title || null
            if (uri && !aggregate.has(uri)) aggregate.set(uri, title)
          })
        } catch(e) { /* continue */ }
      }

      // Explicit lookup for Article 106 if homicide cues present
      const nd = normalize(caseDescription)
      const homicideCue = /muerte inmediata|homicidio|asesinato/.test(nd)
      if (homicideCue) {
        const numQuery = `
PREFIX lo: <http://legalontosystem.pe/ontology#>
SELECT ?art ?titulo WHERE {
  ?art a lo:Articulo ; lo:articleNumber "106" .
  OPTIONAL { ?art lo:titulo ?titulo }
} LIMIT 10`
        try {
          // prefer non-SPARQL direct scan using search_text including article number string
          const resp = await axios.post(`${API_BASE}/search_text`, { keywords: ['106'], limit: 20 })
          const items = Array.isArray(resp.data?.results) ? resp.data.results : []
          items.forEach(it => {
            const uri = normalizeUri(it.res)
            const title = it.title || 'Homicidio simple'
            if (uri && !aggregate.has(uri)) aggregate.set(uri, title)
          })
        } catch (e) {}
      }

      // Finalize recommendations from aggregate
      if (aggregate.size > 0) {
        recs.applicableLaws = Array.from(aggregate.entries()).slice(0, 20).map(([uri, title]) => ({ law: uri, title }))
      }

      // Generate reasoning explanation
      recs.reasoning = `
Análisis del caso:
- Entidades detectadas: ${articles.join(', ') || 'ninguna'}
- Palabras clave: ${keywords.slice(0, 5).join(', ') || 'ninguna'}
- Leyes aplicables encontradas: ${recs.applicableLaws.length}

Recomendación: Revisa la normativa en orden de relevancia. Las leyes listadas contienen artículos que pueden aplicarse al caso descrito.
      `

      setRecommendations(recs)
    }catch(err){
      console.error(err)
      alert('Error en análisis del caso: ' + (err.response?.data?.error || err.message))
    }finally{
      setLoading(false)
    }
  }

  return (
    <div>
      <Card className="border-0 shadow-sm mb-4">
        <Card.Header className="bg-primary text-white">
          <Card.Title className="mb-0">📋 Asesor de Casos Jurídicos</Card.Title>
          <small>Describe un caso y obtén recomendaciones de leyes aplicables</small>
        </Card.Header>
        <Card.Body>
          <Form onSubmit={e => {e.preventDefault(); analyzeCase()}}>
            <Form.Group className="mb-3">
              <Form.Label className="fw-bold">Descripción del Caso</Form.Label>
              <Form.Control
                as="textarea"
                rows={10}
                value={caseDescription}
                onChange={e => setCaseDescription(e.target.value)}
                placeholder="Describe el caso jurídico en detalle. Incluye hechos, fechas, partes involucradas, etc."
                className="border-2 font-monospace"
                style={{fontSize: '0.9rem'}}
              />
              <Form.Text className="text-muted">
                Proporciona toda la información relevante para un análisis completo
              </Form.Text>
            </Form.Group>

            <Button
              variant="primary"
              size="lg"
              type="submit"
              disabled={loading}
              className="w-100"
            >
              {loading ? (
                <>
                  <Spinner animation="border" size="sm" className="me-2" />
                  Analizando...
                </>
              ) : (
                <>
                  <span className="me-2">⚡</span>Analizar y Recomendar
                </>
              )}
            </Button>
          </Form>
        </Card.Body>
      </Card>

      {extractedEntities && (
        <Card className="border-0 shadow-sm mb-4">
          <Card.Header className="bg-info text-white">
            <Card.Title className="mb-0">🔍 Entidades Extraídas</Card.Title>
          </Card.Header>
          <Card.Body>
            <Row className="g-4">
              {extractedEntities.articles && extractedEntities.articles.length > 0 && (
                <Col md={6}>
                  <h5 className="fw-bold mb-3">📑 Artículos Mencionados</h5>
                  <div className="d-flex flex-wrap gap-2">
                    {extractedEntities.articles.map((art, i) => (
                      <Badge key={i} bg="secondary" pill className="fs-6 px-3 py-2">
                        Art. {art}
                      </Badge>
                    ))}
                  </div>
                </Col>
              )}
              {extractedEntities.keywords && extractedEntities.keywords.length > 0 && (
                <Col md={6}>
                  <h5 className="fw-bold mb-3">🏷️ Conceptos Clave</h5>
                  <div className="d-flex flex-wrap gap-2">
                    {extractedEntities.keywords.slice(0, 15).map((kw, i) => (
                      <Badge key={i} bg="warning" text="dark" pill className="fs-6 px-3 py-2">
                        {kw}
                      </Badge>
                    ))}
                  </div>
                </Col>
              )}
            </Row>
          </Card.Body>
        </Card>
      )}

      {recommendations && (
        <>
          <Card className="border-0 shadow-sm mb-4">
            <Card.Header className="bg-light border-bottom">
              <Card.Title className="mb-0">💭 Fundamentación del Análisis</Card.Title>
            </Card.Header>
            <Card.Body>
              <Alert variant="light" className="border">
                <pre style={{fontSize: '0.9rem', whiteSpace: 'pre-wrap'}}>
                  {recommendations.reasoning}
                </pre>
              </Alert>
            </Card.Body>
          </Card>

          <Card className="border-0 shadow-sm mb-4">
            <Card.Header className="bg-success text-white">
              <Card.Title className="mb-0">⚖️ Leyes y Artículos Recomendados</Card.Title>
              <Badge bg="light" text="dark" className="float-end">
                {recommendations.applicableLaws.length} resultado(s)
              </Badge>
            </Card.Header>
            <Card.Body>
              {recommendations.applicableLaws.length > 0 ? (
                <ListGroup className="list-group-flush">
                  {recommendations.applicableLaws.map((item, i) => (
                    <ListGroup.Item key={i} className="d-flex justify-content-between align-items-start py-3">
                      <div className="flex-grow-1">
                        <h6 className="mb-1 fw-bold">{item.title || 'Sin título'}</h6>
                        <small className="text-muted d-block text-break">
                          {item.law}
                        </small>
                      </div>
                      <Badge bg="primary" className="ms-2" pill>
                        {i + 1}
                      </Badge>
                    </ListGroup.Item>
                  ))}
                </ListGroup>
              ) : (
                <Alert variant="warning" className="mb-0">
                  <span className="me-2">⚠️</span>No se encontraron leyes aplicables con los criterios de búsqueda
                </Alert>
              )}
            </Card.Body>
          </Card>
        </>
      )}
    </div>
  )
}

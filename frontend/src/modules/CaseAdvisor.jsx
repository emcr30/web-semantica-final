import React, {useState} from 'react'
import axios from 'axios'
import { Card, Form, Button, Row, Col, Badge, Alert, Spinner, ListGroup } from 'react-bootstrap'

export default function CaseAdvisor({API_BASE}){
  const [caseDescription, setCaseDescription] = useState('')
  const [recommendations, setRecommendations] = useState(null)
  const [loading, setLoading] = useState(false)
  const [extractedEntities, setExtractedEntities] = useState(null)

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

      // Step 2: Search for applicable laws based on entities
      const articles = nlpRes.data.articles || []
      const keywords = nlpRes.data.keywords || []
      
      let recs = {
        entities: nlpRes.data,
        applicableLaws: [],
        reasoning: ''
      }

      // SPARQL query to find laws matching keywords (search in label/titulo/texto)
      if(keywords.length > 0){
        // build a FILTER that matches any keyword in label, titulo or texto
        const safeKw = kw => kw.replace(/"/g,'\\"').replace(/\n/g,' ').trim()
        const filters = keywords.map(k => {
          const sk = safeKw(k)
          return `(regex(str(?label), "${sk}", "i") || regex(str(?titulo), "${sk}", "i") || regex(str(?texto), "${sk}", "i"))`
        }).join(' || ')

        const sparqlQuery = `
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX lo: <http://legalontosystem.pe/ontology#>
SELECT ?res ?label ?titulo ?article ?texto WHERE {
  { ?res a lo:Ley } UNION { ?res a lo:Articulo } .
  OPTIONAL { ?res rdfs:label ?label }
  OPTIONAL { ?res lo:titulo ?titulo }
  OPTIONAL { ?res lo:texto ?texto }
  OPTIONAL { ?res lo:tieneArticulo ?article }
  FILTER ( ${filters} )
} LIMIT 50
        `
        const sparqlRes = await axios.post(`${API_BASE}/sparql`, { query: sparqlQuery })
        // normalize to objects with .law and .title for UI, normalize 'None'/'null'
        recs.applicableLaws = (sparqlRes.data.results || []).map(r => {
          let title = r.label || r['?label'] || r.titulo || r['?titulo'] || null
          if(title && (title.toLowerCase() === 'none' || title.toLowerCase() === 'null')) title = null
          return ({ law: r.res || r['?res'], title: title })
        }).slice(0,20)
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

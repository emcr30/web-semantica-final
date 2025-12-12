import React, {useState, useEffect} from 'react'
import axios from 'axios'
import { Card, Form, Button, Alert, Spinner, Badge, Row, Col, ListGroup } from 'react-bootstrap'

export default function ContradictionDetector({API_BASE}){
  const [contradictions, setContradictions] = useState(null)
  const [loading, setLoading] = useState(false)
  const [selectedLaw, setSelectedLaw] = useState('')
  const [laws, setLaws] = useState([])

  useEffect(() => {
    loadLaws()
    loadAllContradictions()
  }, [])

  async function loadLaws(){
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
        setLaws(lawsList)
      }catch(e){
        const r2 = await axios.get(`${API_BASE}/list_resources`)
        setLaws((r2.data.results||[]).filter(i=>!i.is_part).map(i=>({ uri:i.uri, title:i.title })))
      }
    }catch(err){
      console.error('Error loading laws:', err)
    }
  }

  async function loadAllContradictions(){
    setLoading(true)
    try{
      const res = await axios.get(`${API_BASE}/detect_contradictions`)
      setContradictions(res.data.contradictions || [])
    }catch(err){
      console.error(err)
      alert('Error al detectar contradicciones: ' + err.message)
    }finally{
      setLoading(false)
    }
  }

  async function checkLawContradictions(){
    if(!selectedLaw){
      alert('Por favor selecciona una ley')
      return
    }

    setLoading(true)
    try{
      const sparql = `
  PREFIX lo: <http://legalontosystem.pe/ontology#>
  PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?conflictLaw ?label ?titulo ?relationship WHERE {
    {
      <${selectedLaw}> lo:deroga ?conflictLaw .
      OPTIONAL { ?conflictLaw rdfs:label ?label }
      OPTIONAL { ?conflictLaw lo:titulo ?titulo }
      BIND("deroga" AS ?relationship)
    }
    UNION {
      <${selectedLaw}> lo:modifica ?conflictLaw .
      OPTIONAL { ?conflictLaw rdfs:label ?label }
      OPTIONAL { ?conflictLaw lo:titulo ?titulo }
      BIND("modifica" AS ?relationship)
    }
    UNION {
      <${selectedLaw}> lo:reglamenta ?conflictLaw .
      OPTIONAL { ?conflictLaw rdfs:label ?label }
      OPTIONAL { ?conflictLaw lo:titulo ?titulo }
      BIND("reglamenta" AS ?relationship)
    }
  } LIMIT 50
        `
      const res = await axios.post(`${API_BASE}/sparql`, { query: sparql })
      const results = res.data.results || []
      
      const formatted = results.map(r => ({
        law: selectedLaw,
        conflictLaw: r.conflictLaw || r['?conflictLaw'],
        relationship: r.relationship || r['?relationship'],
        conflictTitle: r.label || r['?label'] || r.titulo || r['?titulo'] || r.conflictLaw || r['?conflictLaw']
      }))
      
      setContradictions(formatted)
    }catch(err){
      console.error(err)
      alert('Error al analizar contradicciones: ' + err.message)
    }finally{
      setLoading(false)
    }
  }

  return (
    <div className="fade-in">
      <Card className="mb-4">
        <Card.Header>
          <Card.Title className="mb-0">Detector de Contradicciones Normativas</Card.Title>
          <small className="text-white-50">Identifica conflictos, derogaciones e inconsistencias entre leyes</small>
        </Card.Header>
        <Card.Body>
          <Form.Group className="mb-3">
            <Form.Label className="fw-bold">Selecciona una Ley para Analizar</Form.Label>
            <Row>
              <Col md="9">
                <Form.Select
                  value={selectedLaw}
                  onChange={e => setSelectedLaw(e.target.value)}
                >
                  <option value="">-- Elige una norma --</option>
                  {laws.map(law => (
                    <option key={law.uri} value={law.uri}>
                      {law.title || law.uri}
                    </option>
                  ))}
                </Form.Select>
              </Col>
              <Col md="3">
                <Button
                  variant="primary"
                  onClick={checkLawContradictions}
                  disabled={loading || !selectedLaw}
                  className="w-100"
                >
                  {loading ? 'Analizando...' : 'Analizar'}
                </Button>
              </Col>
            </Row>
          </Form.Group>

          <Alert variant="secondary">
            <Alert.Heading className="h6 mb-2">O ver análisis completo</Alert.Heading>
            <p className="mb-0">
              <Button
                variant="outline-secondary"
                size="sm"
                onClick={loadAllContradictions}
                disabled={loading}
              >
                {loading ? 'Cargando...' : 'Cargar Todas las Contradicciones'}
              </Button>
            </p>
          </Alert>
        </Card.Body>
      </Card>

      {contradictions && contradictions.length > 0 && (
        <Card className="mb-4">
          <Card.Header>
            <Card.Title className="mb-0">
              Conflictos Detectados
              <Badge bg="danger" className="ms-2">{contradictions.length}</Badge>
            </Card.Title>
          </Card.Header>
          <Card.Body>
            <ListGroup variant="flush">
              {contradictions.map((conflict, i) => (
                <ListGroup.Item key={i} className="p-3 mb-2 border-start border-4 border-danger">
                  <Row className="align-items-start">
                    <Col md="auto" className="mb-3 mb-md-0">
                      <Badge bg="danger">CONFLICTO</Badge>
                    </Col>
                    <Col>
                      <div className="d-flex gap-2 align-items-center mb-2">
                        <Badge bg="warning" text="dark">{conflict.relationship || 'conflicto'}</Badge>
                        <h6 className="mb-0 text-dark">{conflict.conflictTitle || conflict.conflictLaw || 'Ley desconocida'}</h6>
                      </div>
                      {conflict.description && (
                        <p className="mb-2 text-muted small">{conflict.description}</p>
                      )}
                      {conflict.impact && (
                        <Alert variant="danger" className="mb-0 py-2 px-3 small">
                          <strong>Impacto:</strong> {conflict.impact}
                        </Alert>
                      )}
                    </Col>
                    <Col md="auto" className="mt-3 mt-md-0">
                      <Button variant="outline-danger" size="sm">Ver Detalles</Button>
                    </Col>
                  </Row>
                </ListGroup.Item>
              ))}
            </ListGroup>
          </Card.Body>
        </Card>
      )}

      {contradictions && contradictions.length === 0 && !loading && (
        <Alert variant="success">
          <Alert.Heading>Sin conflictos</Alert.Heading>
          <p className="mb-0">No se detectaron contradicciones en el análisis de normas.</p>
        </Alert>
      )}
    </div>
  )
}

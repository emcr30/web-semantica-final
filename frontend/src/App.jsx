import React, {useState, useEffect} from 'react'
import axios from 'axios'
import { Container, Row, Col, Nav, Navbar, Card, Form, Button, Tab, Alert, Spinner, Badge } from 'react-bootstrap'
import D3Graph from './D3Graph'
import CaseAdvisor from './modules/CaseAdvisor'
import PrecedentAnalyzer from './modules/PrecedentAnalyzer'
import HierarchyViewer from './modules/HierarchyViewer'
import ContradictionDetector from './modules/ContradictionDetector'
import PdfUploader from './modules/PdfUploader'
import CaseUploader from './modules/CaseUploader'

export default function App(){
  const [tab, setTab] = useState('search')
  const [query, setQuery] = useState('')
  const [searchScope, setSearchScope] = useState('')
  const [nodes, setNodes] = useState([])
  const [links, setLinks] = useState([])
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState(null)
  const [sparqlQuery, setSparqlQuery] = useState('')
  const [sparqlResult, setSparqlResult] = useState(null)
  const [ingestStatus, setIngestStatus] = useState(null)
 
  // API base allows overriding in Vite (.env) or production builds
  let API_BASE = ''
  try{
    API_BASE = (import.meta && import.meta.env && import.meta.env.VITE_API_BASE) || ''
  }catch(e){ API_BASE = '' }
  if(!API_BASE){
    if(typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')){
      API_BASE = 'http://127.0.0.1:5000'
    }
  }

  async function loadLaws(){
    setLoading(true)
    try{
      const sparql = `PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX lo: <http://legalontosystem.pe/ontology#>\nSELECT ?res ?label ?titulo WHERE { { ?res a lo:Ley } UNION { ?res a lo:Articulo } UNION { ?res a lo:Documento } . OPTIONAL { ?res rdfs:label ?label } OPTIONAL { ?res lo:titulo ?titulo } } LIMIT 200`
      const res = await axios.post(`${API_BASE}/sparql`, { query: sparql })
      const rows = (res.data && (res.data.results || res.data.results)) || []
      const n = []
      rows.forEach((r)=>{
        if(!r) return
        const vals = (typeof r === 'object') ? r : {}
        const uri = vals.res || vals['?res'] || Object.values(vals)[0]
        const title = vals.label || vals['?label'] || vals.titulo || vals['?titulo'] || Object.values(vals)[1] || uri
        if(uri) n.push({ id: uri, label: title || uri })
      })
      const visible = n.filter(item => {
        if(item.is_part) return false
        if((item.id||'').startsWith('http://legalontosystem.pe/resource/')) return false
        const lab = (item.label || '').toString().trim()
        if(!lab) return false
        const ll = lab.toLowerCase()
        if(ll === 'none' || ll === 'null') return false
        if(ll.endsWith('.pdf')) return false
        return true
      })
      setNodes(visible)
      setLinks([])
    }catch(err){
      console.error('SPARQL load failed, attempting fallback list_resources:', err)
      try{
        const res2 = await axios.get(`${API_BASE}/list_resources`)
        const items = (res2.data && res2.data.results) || []
        const visible = items.filter(it => !it.is_part)
        setNodes(visible.map(i => ({ id: i.uri, label: i.title || i.label || i.texto || i.uri })))
        setLinks([])
      }catch(err2){
        console.error(err2)
        alert('Error al cargar las leyes: ' + (err.message || err))
      }
    }finally{ setLoading(false) }
  }

  useEffect(()=>{
    loadLaws()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function search(){
    if(!query) return loadLaws()
    try{
      const scopeParam = searchScope ? `&scope=${encodeURIComponent(searchScope)}` : ''
      const res = await axios.get(`${API_BASE}/search?q=${encodeURIComponent(query)}${scopeParam}`)
      const data = res.data || []
      const filtered = data.filter(item => item.is_part !== true)
      setNodes(filtered.map((r)=>{
        const id = r.uri || r.law || Object.values(r)[0]
        const label = r.label || r.texto || r.title || id
        return { id, label }
      }).filter(item => {
        if((item.id||'').startsWith('http://legalontosystem.pe/resource/')) return false
        const lab = (item.label || '').toString().trim()
        if(!lab) return false
        const ll = lab.toLowerCase()
        if(ll === 'none' || ll === 'null') return false
        if(ll.endsWith('.pdf')) return false
        return true
      }))
      setLinks([])
    }catch(err){
      console.error(err)
      alert('Error en la búsqueda')
    }
  }

  async function doSparql(){
    try{
      const res = await axios.post(`${API_BASE}/sparql`, { query: sparqlQuery })
      setSparqlResult(res.data)
    }catch(err){
      console.error(err)
      alert('Error en consulta SPARQL: '+err.message)
    }
  }

  async function ingestText(text, title, id){
    try{
      const res = await axios.post(`${API_BASE}/ingest`, { text, title, id })
      setIngestStatus(res.data)
      alert('Ingesta completada: '+ JSON.stringify(res.data))
    }catch(err){
      console.error(err)
      alert('Error en la ingesta: '+err.message)
    }
  }

  async function ingestCsv(payload){
    try{
      let res
      if (typeof FormData !== 'undefined' && payload instanceof FormData){
        res = await axios.post(`${API_BASE}/ingest_csv`, payload, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })
      } else {
        res = await axios.post(`${API_BASE}/ingest_csv`, { url: payload })
      }
      setIngestStatus(res.data)
      alert('CSV procesado correctamente: ' + JSON.stringify(res.data))
    }catch(err){
      console.error(err)
      alert('Error al procesar CSV: '+ (err.response?.data || err.message))
    }
  }

  async function fetchEntity(uri){
    try{
      const res = await axios.get(`${API_BASE}/entity`, { params: { uri } })
      setSelected(res.data)
    }catch(err){
      console.error(err)
      alert('Error al obtener entidad: '+ (err.response?.data||err.message))
    }
  }

  return (
    <div className="d-flex flex-column min-vh-100" style={{backgroundColor: '#f5f7fa'}}>
      {/* Header */}
      <Navbar bg="dark" sticky="top" className="navbar-expand-lg shadow-sm" data-bs-theme="dark">
        <Container-fluid className="px-4">
          <Navbar.Brand href="#" className="fw-bold d-flex align-items-center">
            <img src="/seman.jpg" alt="LegalOnto System" className="me-2" style={{height: '34px', width: '34px', objectFit: 'cover', borderRadius: '6px'}} />
            LegalOnto System
          </Navbar.Brand>
          <Navbar.Toggle aria-controls="basic-navbar-nav" />
          <Navbar.Collapse id="basic-navbar-nav" className="justify-content-end">
            <Nav className="align-items-center">
              <span className="text-light me-3">Sistema de Asesoria Jurídica Inteligente</span>
              <Badge bg="success" className="rounded-pill">v1.0</Badge>
            </Nav>
          </Navbar.Collapse>
        </Container-fluid>
      </Navbar>

      {/* Main Content */}
      <Container-fluid className="flex-grow-1 py-4 px-4">
        <Tab.Container activeKey={tab} onSelect={(k) => setTab(k)}>
          {/* Tabs Navigation */}
          <Row className="mb-4">
            <Col>
              <Nav variant="pills" className="flex-wrap gap-2">
                <Nav.Item>
                  <Nav.Link eventKey="search" className="btn-outline-primary">
                    <span className="me-2">🏠</span>Búsqueda
                  </Nav.Link>
                </Nav.Item>
                <Nav.Item>
                  <Nav.Link eventKey="advisor" className="btn-outline-primary">
                    <span className="me-2">📋</span>Asesor de Casos
                  </Nav.Link>
                </Nav.Item>
                <Nav.Item>
                  <Nav.Link eventKey="precedents" className="btn-outline-primary">
                    <span className="me-2">⚖️</span>Precedentes
                  </Nav.Link>
                </Nav.Item>
                <Nav.Item>
                  <Nav.Link eventKey="cases" className="btn-outline-primary">
                    <span className="me-2">🗂️</span>Casos
                  </Nav.Link>
                </Nav.Item>
                <Nav.Item>
                  <Nav.Link eventKey="hierarchy" className="btn-outline-primary">
                    <span className="me-2">🌳</span>Jerarquía
                  </Nav.Link>
                </Nav.Item>
                <Nav.Item>
                  <Nav.Link eventKey="contradictions" className="btn-outline-primary">
                    <span className="me-2">⚠️</span>Contradicciones
                  </Nav.Link>
                </Nav.Item>
                <Nav.Item>
                  <Nav.Link eventKey="ingest" className="btn-outline-primary">
                    <span className="me-2">📥</span>Datos
                  </Nav.Link>
                </Nav.Item>
                <Nav.Item>
                  <Nav.Link eventKey="pdf" className="btn-outline-primary">
                    <span className="me-2">📄</span>Subir PDF
                  </Nav.Link>
                </Nav.Item>
                <Nav.Item>
                  <Nav.Link eventKey="sparql" className="btn-outline-primary">
                    <span className="me-2">⚡</span>SPARQL
                  </Nav.Link>
                </Nav.Item>
              </Nav>
            </Col>
          </Row>

          {/* Tab Content */}
          <Tab.Content>
            {/* Search Tab */}
            <Tab.Pane eventKey="search">
              <div>
                <Card className="border-0 shadow-sm mb-4">
                  <Card.Header className="bg-primary text-white">
                    <Card.Title className="mb-0">Búsqueda y Visualización de Leyes</Card.Title>
                  </Card.Header>
                  <Card.Body>
                    <Form className="mb-3">
                      <Row className="g-3">
                        <Col lg={7}>
                          <Form.Group>
                            <Form.Control
                              type="text"
                              placeholder="Buscar leyes por título o contenido..."
                              value={query}
                              onChange={e => setQuery(e.target.value)}
                              onKeyPress={e => e.key === 'Enter' && search()}
                              size="lg"
                              className="border-2"
                            />
                          </Form.Group>
                        </Col>
                        <Col lg={3}>
                          <Form.Select
                            value={searchScope}
                            onChange={e => setSearchScope(e.target.value)}
                            size="lg"
                            className="border-2"
                          >
                            <option value="">Ámbito: todo</option>
                            <option value="content">Buscar en contenido</option>
                            <option value="keywords">Buscar por keywords (delitos)</option>
                          </Form.Select>
                        </Col>
                        <Col lg={2} className="d-flex gap-2">
                          <Button
                            variant="primary"
                            size="lg"
                            onClick={search}
                            className="flex-grow-1"
                          >
                            <span className="me-2">🔍</span>Buscar
                          </Button>
                          <Button
                            variant="outline-secondary"
                            size="lg"
                            onClick={loadLaws}
                            disabled={loading}
                          >
                            {loading ? <Spinner animation="border" size="sm" className="me-2" /> : ''}
                            Cargar
                          </Button>
                        </Col>
                      </Row>
                    </Form>
                  </Card.Body>
                </Card>

                <Row className="g-4">
                  <Col lg={8}>
                    <Card className="border-0 shadow-sm h-100">
                      <Card.Header className="bg-light border-bottom">
                        <Card.Title className="mb-0">Grafo de Relaciones</Card.Title>
                      </Card.Header>
                      <Card.Body className="p-0">
                        <div style={{height: '500px'}}>
                          <D3Graph
                            nodes={nodes}
                            links={links}
                            width="100%"
                            height="500"
                            onNodeClick={async (n) => {await fetchEntity(n.id)}}
                          />
                        </div>
                      </Card.Body>
                    </Card>
                  </Col>

                  <Col lg={4}>
                    <Card className="border-0 shadow-sm h-100">
                      <Card.Header className="bg-light border-bottom">
                        <Card.Title className="mb-0">Información Detallada</Card.Title>
                      </Card.Header>
                      <Card.Body style={{maxHeight: '600px', overflowY: 'auto'}}>
                        {selected ? (
                          <div>
                            <div className="mb-3">
                              <small className="text-muted d-block mb-1">URI del Recurso</small>
                              <code className="d-block p-2 bg-light rounded text-break" style={{fontSize: '0.85rem'}}>
                                {selected.uri}
                              </code>
                            </div>
                            <hr />
                            <div>
                              <small className="text-muted d-block mb-2">Propiedades</small>
                              {selected.properties.map((p, i) => (
                                <div key={i} className="mb-2 p-2 border-bottom">
                                  <small className="text-primary fw-bold d-block">{p.p}</small>
                                  <small className="text-break">{p.o}</small>
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : (
                          <div className="text-center py-5 text-muted">
                            <div style={{fontSize: '3rem'}} className="mb-3">📄</div>
                            <p>Selecciona un elemento del grafo</p>
                            <small>Haz clic en cualquier nodo para ver sus detalles</small>
                          </div>
                        )}
                      </Card.Body>
                    </Card>
                  </Col>
                </Row>
              </div>
            </Tab.Pane>

            {/* Advisor Tab */}
            <Tab.Pane eventKey="advisor">
              <CaseAdvisor API_BASE={API_BASE} />
            </Tab.Pane>

            {/* Precedents Tab */}
            <Tab.Pane eventKey="precedents">
              <PrecedentAnalyzer API_BASE={API_BASE} />
            </Tab.Pane>

            {/* Cases Tab */}
            <Tab.Pane eventKey="cases">
              <CaseUploader API_BASE={API_BASE} />
            </Tab.Pane>

            {/* Hierarchy Tab */}
            <Tab.Pane eventKey="hierarchy">
              <HierarchyViewer API_BASE={API_BASE} />
            </Tab.Pane>

            {/* Contradictions Tab */}
            <Tab.Pane eventKey="contradictions">
              <ContradictionDetector API_BASE={API_BASE} />
            </Tab.Pane>

            {/* Ingest Tab */}
            <Tab.Pane eventKey="ingest">
              <Row className="g-4">
                <Col lg={6}>
                  <Card className="border-0 shadow-sm h-100">
                    <Card.Header className="bg-primary text-white">
                      <Card.Title className="mb-0">Ingesta Manual de Texto</Card.Title>
                      <small>Agrega documentos legales directamente desde texto</small>
                    </Card.Header>
                    <Card.Body>
                      <IngestForm onIngest={ingestText} />
                    </Card.Body>
                  </Card>
                </Col>

                <Col lg={6}>
                  <Card className="border-0 shadow-sm h-100">
                    <Card.Header className="bg-success text-white">
                      <Card.Title className="mb-0">Importación desde CSV</Card.Title>
                      <small>Carga múltiples documentos desde archivo CSV</small>
                    </Card.Header>
                    <Card.Body>
                      <CsvIngestForm onIngestCsv={ingestCsv} />
                    </Card.Body>
                  </Card>
                </Col>
              </Row>

              {ingestStatus && (
                <Card className="border-0 shadow-sm mt-4 border-left border-success">
                  <Card.Header className="bg-light border-bottom">
                    <Card.Title className="mb-0 text-success">✓ Resultado de la Operación</Card.Title>
                  </Card.Header>
                  <Card.Body>
                    <pre className="mb-0" style={{fontSize: '0.85rem', maxHeight: '400px', overflowY: 'auto'}}>
                      {JSON.stringify(ingestStatus, null, 2)}
                    </pre>
                  </Card.Body>
                </Card>
              )}
            </Tab.Pane>

            {/* PDF Upload Tab */}
            <Tab.Pane eventKey="pdf">
              <Card className="border-0 shadow-sm">
                <Card.Header className="bg-warning text-dark">
                  <Card.Title className="mb-0">Subir y Procesar PDFs</Card.Title>
                  <small>Carga documentos en PDF para análisis automático</small>
                </Card.Header>
                <Card.Body>
                  <PdfUploader apiBase={API_BASE} />
                </Card.Body>
              </Card>
            </Tab.Pane>

            {/* SPARQL Tab */}
            <Tab.Pane eventKey="sparql">
              <Row className="g-4">
                <Col lg={12}>
                  <Card className="border-0 shadow-sm">
                    <Card.Header className="bg-info text-white">
                      <Card.Title className="mb-0">Editor de Consultas SPARQL</Card.Title>
                      <small>Ejecuta consultas personalizadas sobre la base de conocimiento</small>
                    </Card.Header>
                    <Card.Body>
                      <Form.Group className="mb-3">
                        <Form.Label className="fw-bold">Consulta SPARQL</Form.Label>
                        <Form.Control
                          as="textarea"
                          rows={12}
                          value={sparqlQuery}
                          onChange={e => setSparqlQuery(e.target.value)}
                          placeholder="PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>&#10;SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10"
                          className="font-monospace border-2"
                          style={{fontSize: '0.9rem'}}
                        />
                      </Form.Group>
                      <Button
                        variant="info"
                        size="lg"
                        onClick={doSparql}
                        className="w-100"
                      >
                        <span className="me-2">⚡</span>Ejecutar Consulta
                      </Button>
                    </Card.Body>
                  </Card>
                </Col>
              </Row>

              {sparqlResult && (
                <Row className="g-4 mt-4">
                  <Col lg={12}>
                    <Card className="border-0 shadow-sm">
                      <Card.Header className="bg-light border-bottom">
                        <Card.Title className="mb-0">Resultados</Card.Title>
                      </Card.Header>
                      <Card.Body>
                        <pre className="mb-0" style={{fontSize: '0.85rem', maxHeight: '600px', overflowY: 'auto'}}>
                          {JSON.stringify(sparqlResult, null, 2)}
                        </pre>
                      </Card.Body>
                    </Card>
                  </Col>
                </Row>
              )}
            </Tab.Pane>
          </Tab.Content>
        </Tab.Container>
      </Container-fluid>

      {/* Footer */}
      <footer className="bg-dark text-light text-center py-3 mt-5">
        <Container-fluid>
          <small>LegalOnto System © 2025 | Sistema Inteligente de Asesoría Jurídica</small>
        </Container-fluid>
      </footer>
    </div>
  )
}

function IngestForm({onIngest}){
  const [title, setTitle] = useState('')
  const [id, setId] = useState('')
  const [text, setText] = useState('')
 
  return (
    <Form onSubmit={e => {e.preventDefault(); onIngest(text, title, id)}}>
      <Form.Group className="mb-3">
        <Form.Label className="fw-bold">ID de la Norma (opcional)</Form.Label>
        <Form.Control
          type="text"
          placeholder="Ej: LEY-001"
          value={id}
          onChange={e => setId(e.target.value)}
          className="border-2"
        />
        <Form.Text className="text-muted">Identificador único para esta norma</Form.Text>
      </Form.Group>

      <Form.Group className="mb-3">
        <Form.Label className="fw-bold">Título de la Norma</Form.Label>
        <Form.Control
          type="text"
          placeholder="Ej: Ley de Protección de Datos Personales"
          value={title}
          onChange={e => setTitle(e.target.value)}
          className="border-2"
          required
        />
        <Form.Text className="text-muted">Nombre completo de la ley o decreto</Form.Text>
      </Form.Group>

      <Form.Group className="mb-3">
        <Form.Label className="fw-bold">Contenido del Documento</Form.Label>
        <Form.Control
          as="textarea"
          rows={8}
          placeholder="Pegar aquí el texto completo de la norma legal..."
          value={text}
          onChange={e => setText(e.target.value)}
          className="border-2 font-monospace"
          style={{fontSize: '0.9rem'}}
          required
        />
        <Form.Text className="text-muted">Incluye el texto íntegro del documento</Form.Text>
      </Form.Group>

      <Button
        variant="primary"
        size="lg"
        type="submit"
        className="w-100"
      >
        <span className="me-2">✓</span>Procesar e Ingestar
      </Button>
    </Form>
  )
}

function CsvIngestForm({onIngestCsv}){
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)

  async function submitFile(){
    if(!file) {
      alert('Por favor selecciona un archivo CSV')
      return
    }
    setUploading(true)
    try{
      const fd = new FormData()
      fd.append('file', file)
      await onIngestCsv(fd)
      setFile(null)
    }catch(err){
      console.error(err)
      alert('Error al subir el archivo: ' + (err?.response?.data || err.message || err))
    }finally{
      setUploading(false)
    }
  }

  return (
    <Form onSubmit={e => {e.preventDefault(); submitFile()}}>
      <Form.Group className="mb-3">
        <Form.Label className="fw-bold">Archivo CSV</Form.Label>
        <Form.Control
          type="file"
          accept=".csv,text/csv"
          onChange={e => setFile(e.target.files?.[0])}
          className="border-2"
        />
        <Form.Text className="text-muted">
          Formatos soportados: CSV exportado desde datosabiertos.gob.pe u otras fuentes oficiales
        </Form.Text>
      </Form.Group>

      {file && (
        <Alert variant="info" className="mb-3">
          <span className="me-2">📎</span>
          Archivo seleccionado: <strong>{file.name}</strong> ({(file.size / 1024).toFixed(2)} KB)
        </Alert>
      )}

      <Button
        variant="success"
        size="lg"
        type="submit"
        disabled={!file || uploading}
        className="w-100"
      >
        {uploading ? (
          <>
            <Spinner animation="border" size="sm" className="me-2" />
            Procesando...
          </>
        ) : (
          <>
            <span className="me-2">⬆️</span>Cargar y Procesar CSV
          </>
        )}
      </Button>
    </Form>
  )
}
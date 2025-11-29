// App.jsx
import React, {useState} from 'react'
import axios from 'axios'
import D3Graph from './D3Graph'

export default function App(){
  const [tab, setTab] = useState('search')
  const [query, setQuery] = useState('')
  const [nodes, setNodes] = useState([])
  const [links, setLinks] = useState([])
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState(null)
  const [sparqlQuery, setSparqlQuery] = useState('')
  const [sparqlResult, setSparqlResult] = useState(null)
  const [ingestStatus, setIngestStatus] = useState(null)
 
  // API base allows overriding in Vite (.env) or production builds
  const API_BASE = (import.meta && import.meta.env && import.meta.env.VITE_API_BASE) || ''

  async function loadLaws(){
    setLoading(true)
    try{
      const sparql = `PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX ex: <http://example.org/legal#>\nSELECT ?law ?title WHERE { ?law a ex:Ley ; rdfs:label ?title } LIMIT 200`
      const res = await axios.post(`${API_BASE}/sparql`, { query: sparql })
      const rows = (res.data && (res.data.results || res.data.results)) || []
      const n = []
      rows.forEach((r, idx)=>{
        const law = r.law || r['?law'] || Object.values(r)[0]
        const title = r.title || r['?title'] || Object.values(r)[1] || law
        n.push({ id: law, label: title })
      })
      setNodes(n)
      setLinks([])
    }catch(err){
      console.error(err)
      alert('Error al cargar las leyes: ' + (err.message || err))
    }finally{ setLoading(false) }
  }

  async function search(){
    if(!query) return loadLaws()
    try{
      const res = await axios.get(`${API_BASE}/search?q=${encodeURIComponent(query)}`)
      const data = res.data || []
      setNodes(data.map((r)=>({ id:r.law || Object.values(r)[0], label:r.title || Object.values(r)[1]})))
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
    <div className="layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="brand">
            <div className="brand-icon">⚖️</div>
            <div className="brand-text">
              <h1>LegalOnto</h1>
              <span className="version">v1.0</span>
            </div>
          </div>
        </div>

        <nav className="sidebar-nav">
          <button
            onClick={()=>setTab('search')}
            className={`nav-item ${tab==='search'?'active':''}`}
          >
            <span className="nav-icon">🏠</span>
            <span>Consulta de Leyes</span>
          </button>

          <button
            onClick={()=>setTab('ingest')}
            className={`nav-item ${tab==='ingest'?'active':''}`}
          >
            <span className="nav-icon">📥</span>
            <span>Ingesta de Datos</span>
          </button>

          <button
            onClick={()=>setTab('sparql')}
            className={`nav-item ${tab==='sparql'?'active':''}`}
          >
            <span className="nav-icon">⚡</span>
            <span>Consultas SPARQL</span>
          </button>
        </nav>
      </aside>

      {/* Main Content */}
      <div className="main">
        {/* Top Bar */}
        <header className="topbar">
          <div className="topbar-content">
            <h2 className="page-title">
              {tab==='search' && 'Búsqueda y Visualización'}
              {tab==='ingest' && 'Gestión de Datos'}
              {tab==='sparql' && 'Editor SPARQL'}
            </h2>
            <div className="user-info">
              <span className="user-name">Sistema Jurídico</span>
              <div className="user-avatar">SJ</div>
            </div>
          </div>
        </header>

        {/* Content Area */}
        <main className="content">
          {/* Search Tab */}
          {tab==='search' && (
            <>
              <div className="section-card">
                <div className="search-container">
                  <input
                    type="text"
                    placeholder="Buscar leyes por título o contenido..."
                    value={query}
                    onChange={e=>setQuery(e.target.value)}
                    onKeyPress={e => e.key === 'Enter' && search()}
                    className="search-field"
                  />
                  <button onClick={search} className="btn-search">
                    Buscar
                  </button>
                  <button
                    onClick={loadLaws}
                    disabled={loading}
                    className="btn-load"
                  >
                    {loading ? 'Cargando...' : 'Cargar todas'}
                  </button>
                </div>
              </div>

              <div className="workspace">
                <div className="graph-container">
                  <div className="card-header">
                    <h3>Grafo de Relaciones</h3>
                  </div>
                  <div className="card-body">
                    <D3Graph
                      nodes={nodes}
                      links={links}
                      width={700}
                      height={500}
                      onNodeClick={async (n)=>{await fetchEntity(n.id)}}
                    />
                  </div>
                </div>

                <div className="details-container">
                  <div className="card-header">
                    <h3>Información Detallada</h3>
                  </div>
                  <div className="card-body">
                    {selected ? (
                      <div className="entity-details">
                        <div className="detail-section">
                          <label>URI del Recurso</label>
                          <div className="uri-display">{selected.uri}</div>
                        </div>
                       
                        <div className="detail-section">
                          <label>Propiedades</label>
                          <div className="properties">
                            {selected.properties.map((p,i)=>(
                              <div key={i} className="property-row">
                                <span className="prop-name">{p.p}</span>
                                <span className="prop-value">{p.o}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="empty-details">
                        <div className="empty-icon">📄</div>
                        <p>Selecciona un elemento del grafo</p>
                        <span>Haz clic en cualquier nodo para ver sus detalles</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Ingest Tab */}
          {tab==='ingest' && (
            <div className="ingest-layout">
              <div className="section-card">
                <div className="card-header">
                  <h3>Ingesta Manual de Texto</h3>
                  <p>Agrega documentos legales directamente desde texto</p>
                </div>
                <div className="card-body">
                  <IngestForm onIngest={ingestText} />
                </div>
              </div>

              <div className="section-card">
                <div className="card-header">
                  <h3>Importación desde CSV</h3>
                  <p>Carga múltiples documentos desde archivo CSV</p>
                </div>
                <div className="card-body">
                  <CsvIngestForm onIngestCsv={ingestCsv} />
                </div>
              </div>

              {ingestStatus && (
                <div className="section-card status-card">
                  <div className="card-header">
                    <h3>✓ Resultado de la Operación</h3>
                  </div>
                  <div className="card-body">
                    <pre className="status-output">
                      {JSON.stringify(ingestStatus, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* SPARQL Tab */}
          {tab==='sparql' && (
            <div className="sparql-layout">
              <div className="section-card">
                <div className="card-header">
                  <h3>Editor de Consultas SPARQL</h3>
                  <p>Ejecuta consultas personalizadas sobre la base de conocimiento</p>
                </div>
                <div className="card-body">
                  <textarea
                    value={sparqlQuery}
                    onChange={e=>setSparqlQuery(e.target.value)}
                    rows={12}
                    placeholder="PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>&#10;SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10"
                    className="sparql-editor"
                  />
                  <button onClick={doSparql} className="btn-execute">
                    Ejecutar Consulta
                  </button>
                </div>
              </div>
             
              {sparqlResult && (
                <div className="section-card">
                  <div className="card-header">
                    <h3>Resultados</h3>
                  </div>
                  <div className="card-body">
                    <pre className="sparql-output">
                      {JSON.stringify(sparqlResult, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  )
}

function IngestForm({onIngest}){
  const [title, setTitle] = useState('')
  const [id, setId] = useState('')
  const [text, setText] = useState('')
 
  return (
    <div className="ingest-form">
      <div className="form-group-row">
        <div className="form-group">
          <label>ID (opcional)</label>
          <input
            type="text"
            placeholder="Ej: LEY-001"
            value={id}
            onChange={e=>setId(e.target.value)}
            className="form-control"
          />
        </div>
        <div className="form-group">
          <label>Título de la norma</label>
          <input
            type="text"
            placeholder="Ej: Ley de Protección de Datos Personales"
            value={title}
            onChange={e=>setTitle(e.target.value)}
            className="form-control"
          />
        </div>
      </div>
     
      <div className="form-group">
        <label>Contenido del documento</label>
        <textarea
          placeholder="Pegar aquí el texto completo de la norma legal..."
          value={text}
          onChange={e=>setText(e.target.value)}
          rows={10}
          className="form-control textarea"
        />
      </div>
     
      <button onClick={()=>onIngest(text,title,id)} className="btn-submit">
        Procesar e Ingestar
      </button>
    </div>
  )
}

function CsvIngestForm({onIngestCsv}){
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)

  async function submitFile(){
    if(!file) return alert('Por favor selecciona un archivo CSV')
    setUploading(true)
    try{
      const fd = new FormData()
      fd.append('file', file)
      await onIngestCsv(fd)
    }catch(err){
      console.error(err)
      alert('Error al subir el archivo: ' + (err?.response?.data || err.message || err))
    }finally{
      setUploading(false)
    }
  }

  return (
    <div className="csv-form">
      <div className="form-group">
        <label>Archivo CSV</label>
        <div className="file-input-wrapper">
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={e=>setFile(e.target.files[0])}
            className="file-input"
            id="csv-file"
          />
          <label htmlFor="csv-file" className="file-label">
            {file ? file.name : 'Seleccionar archivo CSV'}
          </label>
        </div>
      </div>
     
      <button onClick={submitFile} className="btn-submit" disabled={uploading}>
        {uploading ? 'Procesando...' : 'Cargar y Procesar CSV'}
      </button>
     
      <div className="help-text">
        <span className="help-icon">💡</span>
        <p>Formatos soportados: CSV exportado desde datosabiertos.gob.pe u otras fuentes oficiales</p>
      </div>
    </div>
  )
}


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
        // Normalize row access: prefer named vars, fall back to value order
        const law = r.law || r['?law'] || Object.values(r)[0]
        const title = r.title || r['?title'] || Object.values(r)[1] || law
        n.push({ id: law, label: title })
      })
      setNodes(n)
      setLinks([])
    }catch(err){
      console.error(err)
      alert('Error fetching laws: ' + (err.message || err))
    }finally{ setLoading(false) }
  }

  async function search(){
    if(!query) return loadLaws()
    try{
      const res = await axios.get(`${API_BASE}/search?q=${encodeURIComponent(query)}`)
      const data = res.data || []
      setNodes(data.map((r)=>({ id:r.law || Object.values(r)[0], label:r.title || Object.values(r)[1]})))
      setLinks([])
    }catch(err){ console.error(err); alert('Search error') }
  }

  async function doSparql(){
    try{
      const res = await axios.post(`${API_BASE}/sparql`, { query: sparqlQuery })
      setSparqlResult(res.data)
    }catch(err){ console.error(err); alert('SPARQL error: '+err.message) }
  }

  async function ingestText(text, title, id){
    try{
      const res = await axios.post(`${API_BASE}/ingest`, { text, title, id })
      setIngestStatus(res.data)
      alert('Ingested: '+ JSON.stringify(res.data))
    }catch(err){ console.error(err); alert('Ingest error: '+err.message) }
  }

  async function ingestCsv(payload){
    try{
      let res
      if (typeof FormData !== 'undefined' && payload instanceof FormData){
        // send multipart/form-data
        res = await axios.post(`${API_BASE}/ingest_csv`, payload, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })
      } else {
        // assume payload is a URL string
        res = await axios.post(`${API_BASE}/ingest_csv`, { url: payload })
      }
      setIngestStatus(res.data)
      alert('CSV ingested: ' + JSON.stringify(res.data))
    }catch(err){ console.error(err); alert('CSV ingest error: '+ (err.response?.data || err.message)) }
  }

  async function fetchEntity(uri){
    try{
      const res = await axios.get(`${API_BASE}/entity`, { params: { uri } })
      setSelected(res.data)
    }catch(err){ console.error(err); alert('Entity fetch error: '+ (err.response?.data||err.message)) }
  }

  const tabs = [
    { id: 'search', label: 'Búsqueda', icon: '🔍' },
    { id: 'ingest', label: 'Ingestión', icon: '📥' },
    { id: 'sparql', label: 'SPARQL', icon: '⚡' }
  ]

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="header-content">
          <div className="logo-container">
            <div className="logo-icon">⚖️</div>
            <div>
              <h1 className="app-title">LegalOntoSystem</h1>
              <p className="app-subtitle">Sistema de Ontologías Jurídicas</p>
            </div>
          </div>
        </div>
      </header>

      <div className="main-content">
        {/* Tabs */}
        <div className="tabs-container">
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={()=>setTab(t.id)}
              className={`tab-button ${tab === t.id ? 'tab-active' : ''}`}
            >
              <span className="tab-icon">{t.icon}</span>
              {t.label}
            </button>
          ))}
        </div>

        {/* Search Tab */}
        {tab==='search' && (
          <div>
            <div className="search-box">
              <div className="search-controls">
                <input 
                  placeholder="Buscar leyes por texto..." 
                  value={query} 
                  onChange={e=>setQuery(e.target.value)}
                  onKeyPress={e => e.key === 'Enter' && search()}
                  className="search-input"
                />
                <button onClick={search} className="btn btn-primary">
                  Buscar
                </button>
                <button onClick={loadLaws} disabled={loading} className="btn btn-secondary">
                  {loading ? 'Cargando...' : 'Cargar Todas'}
                </button>
              </div>
            </div>

            <div className="content-grid">
              <div className="graph-panel">
                <h3 className="panel-title">
                  <span className="panel-icon graph-icon">📊</span>
                  Grafo de Relaciones
                </h3>
                <D3Graph nodes={nodes} links={links} width={700} height={500} onNodeClick={async (n)=>{await fetchEntity(n.id)}} />
              </div>

              <div className="details-panel">
                <h3 className="panel-title">
                  <span className="panel-icon details-icon">📋</span>
                  Detalles
                </h3>
                {selected ? (
                  <div>
                    <div className="uri-box">
                      <p className="uri-label">URI</p>
                      <p className="uri-value">{selected.uri}</p>
                    </div>
                    <div className="properties-list">
                      {selected.properties.map((p,i)=>(
                        <div key={i} className="property-item">
                          <p className="property-label">{p.p}</p>
                          <p className="property-value">{p.o}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="empty-state">
                    <div className="empty-icon">🔍</div>
                    <p className="empty-text">Selecciona un nodo en el grafo para ver sus detalles</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Ingest Tab */}
        {tab==='ingest' && (
          <div className="ingest-container">
            <div className="card">
              <h3 className="panel-title">
                <span className="panel-icon ingest-icon">📝</span>
                Ingestar Texto Manual
              </h3>
              <IngestForm onIngest={ingestText} />
            </div>

            <div className="card">
              <h3 className="panel-title">
                <span className="panel-icon csv-icon">📊</span>
                Ingestar desde CSV
              </h3>
              <CsvIngestForm onIngestCsv={ingestCsv} />
            </div>

            {ingestStatus && (
              <div className="status-box">
                <h4 className="status-title">✓ Estado de Ingestión</h4>
                <pre className="status-content">
                  {JSON.stringify(ingestStatus, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}

        {/* SPARQL Tab */}
        {tab==='sparql' && (
          <div className="card">
            <h3 className="panel-title">
              <span className="panel-icon sparql-icon">⚡</span>
              Consola SPARQL
            </h3>
            <textarea 
              value={sparqlQuery} 
              onChange={e=>setSparqlQuery(e.target.value)}
              rows={10}
              placeholder="PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>&#10;SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10"
              className="sparql-textarea"
            />
            <button onClick={doSparql} className="btn btn-sparql">
              Ejecutar Consulta
            </button>
            
            {sparqlResult && (
              <div className="sparql-result">
                <p className="result-label">Resultado:</p>
                <pre className="result-content">
                  {JSON.stringify(sparqlResult, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="app-footer">
        <p>© LegalOntoSystem • Gestión Jurídica</p>
      </footer>
    </div>
  )
}

function IngestForm({onIngest}){
  const [title, setTitle] = useState('')
  const [id, setId] = useState('')
  const [text, setText] = useState('')
  
  return (
    <div className="form-container">
      <div className="form-row">
        <input 
          placeholder="ID (opcional)" 
          value={id} 
          onChange={e=>setId(e.target.value)}
          className="form-input"
        />
        <input 
          placeholder="Título de la norma" 
          value={title} 
          onChange={e=>setTitle(e.target.value)}
          className="form-input"
        />
      </div>
      <textarea 
        placeholder="Pegar texto completo de la norma aquí..." 
        value={text} 
        onChange={e=>setText(e.target.value)}
        rows={8}
        className="form-textarea"
      />
      <button onClick={()=>onIngest(text,title,id)} className="btn btn-ingest">
        Ingestar Texto
      </button>
    </div>
  )
}

function CsvIngestForm({onIngestCsv}){
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)

  async function submitFile(){
    if(!file) return alert('Selecciona un archivo CSV primero')
    setUploading(true)
    try{
      const fd = new FormData()
      fd.append('file', file)
      // onIngestCsv can accept FormData; backend will detect file upload
      await onIngestCsv(fd)
    }catch(err){
      console.error(err)
      alert('Error subiendo CSV: ' + (err?.response?.data || err.message || err))
    }finally{
      setUploading(false)
    }
  }

  return (
    <div className="form-container">
      <input 
        type="file"
        accept=".csv,text/csv"
        onChange={e=>setFile(e.target.files[0])}
        className="form-input full-width"
      />
      <button onClick={submitFile} className="btn btn-csv" disabled={uploading}>
        {uploading ? 'Subiendo...' : 'Subir e Ingestar CSV'}
      </button>
      <p className="form-tip">
        💡 Tip: Sube un archivo CSV exportado desde datosabiertos.gob.pe u otra fuente confiable.
      </p>
    </div>
  )
}
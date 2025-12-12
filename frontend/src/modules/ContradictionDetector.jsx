import React, {useState, useEffect} from 'react'
import axios from 'axios'

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
      // Query to find derogations and potential conflicts
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
    <div className="module-container">
      <div className="section-card">
        <div className="card-header">
          <h3>⚠️ Detector de Contradicciones Normativas</h3>
          <p>Identifica conflictos, derogaciones e inconsistencias entre normas</p>
        </div>
        <div className="card-body">
          <div className="form-group">
            <label>Selecciona una Ley para Analizar</label>
            <div style={{display: 'flex', gap: '8px'}}>
              <select
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
              </select>
              <button
                onClick={checkLawContradictions}
                disabled={loading || !selectedLaw}
                className="btn-submit"
                style={{flex: '0 0 auto'}}
              >
                {loading ? 'Analizando...' : 'Analizar'}
              </button>
            </div>
          </div>

          <div className="help-text">
            <p>O visualiza el sistema completo de contradicciones detectadas automáticamente:</p>
            <button
              onClick={loadAllContradictions}
              disabled={loading}
              className="btn-secondary"
            >
              {loading ? 'Cargando...' : 'Cargar Todas las Contradicciones'}
            </button>
          </div>
        </div>
      </div>

      {contradictions && contradictions.length > 0 && (
        <div className="section-card">
          <div className="card-header">
            <h3>🔍 Conflictos Detectados ({contradictions.length})</h3>
          </div>
          <div className="card-body">
            {contradictions.map((conflict, i) => (
              <div key={i} className="contradiction-item">
                <div className="contradiction-severity">
                  <span className="severity-badge high">Alto</span>
                </div>
                <div className="contradiction-content">
                  <div className="contradiction-laws">
                    <span className="law-badge">{conflict.relationship || 'conflicto'}</span>
                    <span className="law-name">{conflict.conflictTitle || conflict.conflictLaw || 'Ley desconocida'}</span>
                  </div>
                  {conflict.description && (
                    <p className="contradiction-desc">{conflict.description}</p>
                  )}
                  {conflict.impact && (
                    <div className="contradiction-impact">
                      <strong>Impacto:</strong> {conflict.impact}
                    </div>
                  )}
                </div>
                <div className="contradiction-action">
                  <button className="btn-small">Ver Detalles</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {contradictions && contradictions.length === 0 && !loading && (
        <div className="section-card">
          <div className="card-body">
            <p className="no-results">✓ No se detectaron contradicciones en el análisis</p>
          </div>
        </div>
      )}
    </div>
  )
}

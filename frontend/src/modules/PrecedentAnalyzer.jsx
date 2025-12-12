import React, {useState, useEffect} from 'react'
import axios from 'axios'

export default function PrecedentAnalyzer({API_BASE}){
  const [selectedLaw, setSelectedLaw] = useState('')
  const [laws, setLaws] = useState([])
  const [precedents, setPrecedents] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadLawsList()
    // listen for case uploads to refresh results when appropriate
    const handler = (e) => {
      // if a law/article is selected, refresh precedents to include newly uploaded cases
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
          // filter out file-like entries and empty/none titles
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
        // fallback to REST list; filter out document parts
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
      // enrich top results with entity metadata (label, jurisdiction, delitoLiteral)
      const enriched = []
      const maxEnrich = 10
      for(let i=0;i<items.length;i++){
        const it = items[i]
        const out = { ...it }
        if(i < maxEnrich){
          try{
            const er = await axios.get(`${API_BASE}/entity`, { params: { uri: it.case } })
            const props = er.data.properties || []
            // map common properties
            props.forEach(p => {
              if(p.p.endsWith('#label') || p.p.endsWith('/rdfs/label')) out.title = out.title || p.o
              if(p.p.endsWith('jurisdiccionCaso')) out.jurisdiction = out.jurisdiction || p.o
              if(p.p.endsWith('fechaSentencia')) out.date = out.date || p.o
              if(p.p.endsWith('delitoLiteral')){
                out.crime = out.crime || p.o
              }
                    // detect uploaded filename property or label that is a PDF
                    if(p.p.endsWith('archivoFilename') || (p.o && p.o.toLowerCase && p.o.toLowerCase().endsWith('.pdf'))){
                      const fname = p.o
                      try{
                        out.pdf = `${API_BASE.replace(/\/$/, '')}/files/${encodeURIComponent(fname)}`
                      }catch(e){ }
                    }
            })
          }catch(e){ /* ignore enrichment errors */ }
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

  return (
    <div className="module-container">
      <div className="section-card">
        <div className="card-header">
          <h3>⚖️ Análisis de Precedentes</h3>
          <p>Encuentra casos relacionados y precedentes jurisprudenciales</p>
        </div>
        <div className="card-body">
          <div className="form-group">
            <label>Selecciona una Ley o Artículo</label>
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
          </div>
          <button
            onClick={findPrecedents}
            disabled={loading || !selectedLaw}
            className="btn-submit"
          >
            {loading ? 'Buscando...' : 'Buscar Precedentes'}
          </button>
        </div>
      </div>

      {precedents && precedents.length > 0 && (
        <div className="section-card">
          <div className="card-header">
            <h3>📑 Precedentes Encontrados ({precedents.length})</h3>
          </div>
          <div className="card-body">
            <div className="precedents-list">
              {precedents.map((prec, i) => (
                <div key={i} className="precedent-item">
                  <div className="precedent-rank">
                    <span className="rank-number">#{i+1}</span>
                    {prec.score && (
                      <span className="rank-score">Score: {(prec.score * 100).toFixed(0)}%</span>
                    )}
                  </div>
                  <div className="precedent-content">
                    <h4>{prec.title || prec.case_id || 'Caso sin título'}</h4>
                    {prec.description && (
                      <p className="precedent-desc">{prec.description}</p>
                    )}
                    {prec.pdf && (
                      <div className="precedent-pdf">
                        <a href={prec.pdf} target="_blank" rel="noreferrer" className="btn-view-pdf">Ver PDF</a>
                        <div className="pdf-preview" style={{marginTop: '8px'}}>
                          <iframe src={prec.pdf} title={`pdf-preview-${i}`} width="100%" height="240px" />
                        </div>
                      </div>
                    )}
                    {prec.jurisdiction && (
                      <div className="precedent-meta">
                        <span>📍 {prec.jurisdiction}</span>
                      </div>
                    )}
                    {prec.date && (
                      <div className="precedent-meta">
                        <span>📅 {prec.date}</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {precedents && precedents.length === 0 && (
        <div className="section-card">
          <div className="card-body">
            <p className="no-results">No se encontraron precedentes para la norma seleccionada</p>
          </div>
        </div>
      )}
    </div>
  )
}

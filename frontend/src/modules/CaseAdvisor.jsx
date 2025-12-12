import React, {useState} from 'react'
import axios from 'axios'

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

      // SPARQL query to find laws
      if(keywords.length > 0){
        const sparqlQuery = `
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX lo: <http://legalontosystem.pe/ontology#>
SELECT ?res ?label ?titulo ?article WHERE {
  { ?res a lo:Ley } UNION { ?res a lo:Articulo } UNION { ?res a lo:Documento } .
  OPTIONAL { ?res rdfs:label ?label }
  OPTIONAL { ?res lo:titulo ?titulo }
  OPTIONAL { ?res lo:tieneArticulo ?article }
} LIMIT 50
        `
        const sparqlRes = await axios.post(`${API_BASE}/sparql`, { query: sparqlQuery })
        // normalize to objects with .law and .title for UI
        recs.applicableLaws = (sparqlRes.data.results || []).map(r => ({ law: r.res || r['?res'], title: r.label || r['?label'] || r.titulo || r['?titulo'] })).slice(0,20)
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
    <div className="module-container">
      <div className="section-card">
        <div className="card-header">
          <h3>📋 Asesor de Casos Jurídicos</h3>
          <p>Describe un caso y obten recomendaciones de leyes aplicables</p>
        </div>
        <div className="card-body">
          <div className="form-group">
            <label>Descripción del Caso</label>
            <textarea
              value={caseDescription}
              onChange={e => setCaseDescription(e.target.value)}
              rows={10}
              placeholder="Describe el caso jurídico en detalle. Incluye hechos, fechas, partes involucradas, etc."
              className="form-control textarea"
            />
          </div>
          <button
            onClick={analyzeCase}
            disabled={loading}
            className="btn-submit"
          >
            {loading ? 'Analizando...' : 'Analizar y Recomendar'}
          </button>
        </div>
      </div>

      {extractedEntities && (
        <div className="section-card">
          <div className="card-header">
            <h3>🔍 Entidades Extraídas</h3>
          </div>
          <div className="card-body">
            <div className="entities-grid">
              {extractedEntities.articles && extractedEntities.articles.length > 0 && (
                <div className="entity-group">
                  <h4>Artículos Mencionados</h4>
                  <ul>
                    {extractedEntities.articles.map((art, i) => (
                      <li key={i}>{art}</li>
                    ))}
                  </ul>
                </div>
              )}
              {extractedEntities.keywords && extractedEntities.keywords.length > 0 && (
                <div className="entity-group">
                  <h4>Conceptos Clave</h4>
                  <div className="keywords-cloud">
                    {extractedEntities.keywords.slice(0, 15).map((kw, i) => (
                      <span key={i} className="keyword-badge">{kw}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {recommendations && (
        <div className="section-card">
          <div className="card-header">
            <h3>⚖️ Leyes Recomendadas</h3>
          </div>
          <div className="card-body">
            <div className="reasoning-box">
              <h4>Fundamentación</h4>
              <p>{recommendations.reasoning}</p>
            </div>

            {recommendations.applicableLaws.length > 0 ? (
              <div className="laws-list">
                {recommendations.applicableLaws.map((law, i) => (
                  <div key={i} className="law-item">
                    <div className="law-title">{i+1}. {law.title || law.law}</div>
                    {law.article && (
                      <div className="law-article">Artículo: {law.article}</div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="no-results">No se encontraron leyes aplicables para este caso</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

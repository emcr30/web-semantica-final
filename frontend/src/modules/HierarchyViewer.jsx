import React, {useState, useEffect, useRef} from 'react'
import axios from 'axios'
import * as d3 from 'd3'

export default function HierarchyViewer({API_BASE}){
  const [hierarchyData, setHierarchyData] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadHierarchy()
  }, [])

  async function loadHierarchy(){
    setLoading(true)
    try{
      // Fetch list of laws & articles (excluding Documento resources)
      const listRes = await axios.get(`${API_BASE}/list_resources`)
      const items = (listRes.data && listRes.data.results) || []
      // Build a map of laws (we will query each law for its articles)
      const laws = items.filter(i => i.uri && i.title)
      const lawMap = {}
      // For each law, fetch its articles via SPARQL
      await Promise.all(laws.map(async (l) => {
        lawMap[l.uri] = { name: l.title, children: [] }
        try{
          const q = `PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX lo: <http://legalontosystem.pe/ontology#>\nPREFIX dct: <http://purl.org/dc/terms/>\nSELECT ?art ?label ?titulo ?anio ?jurisd WHERE { OPTIONAL { <${l.uri}> lo:tieneArticulo ?art . OPTIONAL { ?art rdfs:label ?label } } OPTIONAL { <${l.uri}> lo:titulo ?titulo } OPTIONAL { <${l.uri}> lo:anio ?anio } OPTIONAL { <${l.uri}> lo:aplicaEn ?jurisd } } LIMIT 200`;
          const r = await axios.post(`${API_BASE}/sparql`, { query: q })
          const rows = (r.data && r.data.results) || []
          rows.forEach(row => {
            const artUri = row.art || row['?art']
            const artLabel = row.label || row['?label'] || 'Artículo'
            if(artUri){
              lawMap[l.uri].children.push({ name: artLabel, uri: artUri })
            }
            // attach metadata at top-level law node
            if(row.titulo || row['?titulo']) lawMap[l.uri].title = row.titulo || row['?titulo']
            if(row.anio || row['?anio']) lawMap[l.uri].year = row.anio || row['?anio']
            if(row.jurisd || row['?jurisd']) lawMap[l.uri].jurisdiccion = row.jurisd || row['?jurisd']
          })
          // if no children found, remove this item from top-level (it's probably an Article)
          if((lawMap[l.uri].children || []).length === 0){
            delete lawMap[l.uri]
          }
        }catch(e){
          // ignore per-law errors and continue
          delete lawMap[l.uri]
        }
      }))

      const tree = { name: 'Ordenamiento Jurídico', children: Object.values(lawMap) }
      setHierarchyData(tree)
    }catch(err){
      console.error(err)
    }finally{
      setLoading(false)
    }
  }

  return (
    <div className="module-container">
      <div className="section-card">
        <div className="card-header">
          <h3>🌳 Jerarquía de Normas Legales</h3>
          <p>Visualiza la estructura de leyes, decretos y artículos</p>
        </div>
        <div className="card-body">
          {loading && <p>Cargando estructura...</p>}
          {hierarchyData && (
            <HierarchyTree data={hierarchyData} />
          )}
          {!loading && !hierarchyData && (
            <p>No se pudieron cargar los datos jerárquicos</p>
          )}
        </div>
      </div>

      <div className="section-card">
        <div className="card-header">
          <h3>📊 Estadísticas</h3>
        </div>
        <div className="card-body">
          {hierarchyData && (
            <div className="stats-grid">
              <div className="stat-box">
                <span className="stat-label">Leyes Cargadas</span>
                <span className="stat-value">{hierarchyData.children?.length || 0}</span>
              </div>
              <div className="stat-box">
                <span className="stat-label">Artículos Totales</span>
                <span className="stat-value">
                  {hierarchyData.children?.reduce((sum, ley) => sum + (ley.children?.length || 0), 0) || 0}
                </span>
              </div>
            </div>
          )}
          {hierarchyData && (
            <div className="metadata-list">
              <h4>Metadatos (ejemplo)</h4>
              <ul>
                {hierarchyData.children.slice(0,10).map((l,i)=>(
                  <li key={i}>
                    <strong>{l.name}</strong>
                    {l.year && <span> — Año: {String(l.year)}</span>}
                    {l.jurisdiccion && <span> — Jurisd: {String(l.jurisdiccion)}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function HierarchyTree({data}){
  const width = 900
  const height = 600

  useEffect(() => {
    if(!data) return

    const svg = d3.select('.hierarchy-svg')
    svg.selectAll('*').remove()

    // root viewport group that will be transformed by zoom/pan
    const viewport = svg.append('g').attr('class','viewport')
    const g = viewport.append('g')
      .attr('transform', `translate(${width/2},40)`)

    // setup zoom/pan on svg, transform the viewport group
    const zoom = d3.zoom()
      .scaleExtent([0.2, 4])
      .on('zoom', (event) => {
        viewport.attr('transform', event.transform)
      })
    svg.call(zoom)

    const tree = d3.tree().size([width - 100, height - 100])
    const root = d3.hierarchy(data)
    const links = tree(root).links()
    const nodes = root.descendants()

    // Draw links
    g.append('g')
      .attr('stroke', '#cbd5e1')
      .attr('stroke-opacity', 0.6)
      .selectAll('path')
      .data(links)
      .join('path')
      .attr('d', d3.linkVertical()
        .x(d => d.x)
        .y(d => d.y))

    // Draw nodes
    const nodeG = g.append('g')
      .selectAll('g')
      .data(nodes)
      .join('g')
      .attr('transform', d => `translate(${d.x},${d.y})`)

    nodeG.append('circle')
      .attr('r', d => d.data.children ? 8 : 5)
      .attr('fill', d => d.data.children ? '#1e40af' : '#3b82f6')
      .attr('stroke', '#fff')
      .attr('stroke-width', 1.5)

    nodeG.append('text')
      .attr('x', d => d.data.children ? 0 : 0)
      .attr('y', -15)
      .attr('text-anchor', 'middle')
      .style('font-size', d => d.data.children ? '12px' : '10px')
      .style('fill', '#334155')
      .text(d => (d.data.name || 'N/A').substring(0, 30))
  }, [data])

  return (
    <div className="hierarchy-wrapper">
      <svg className="hierarchy-svg" width={width} height={height}></svg>
    </div>
  )
}

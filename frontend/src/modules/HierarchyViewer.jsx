import React, {useState, useEffect, useRef} from 'react'
import axios from 'axios'
import * as d3 from 'd3'
import { Card, Row, Col, Spinner, Alert } from 'react-bootstrap'

export default function HierarchyViewer({API_BASE}){
  const [hierarchyData, setHierarchyData] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadHierarchy()
  }, [])

  async function loadHierarchy(){
    setLoading(true)
    try{
      const listRes = await axios.get(`${API_BASE}/list_resources`)
      const items = (listRes.data && listRes.data.results) || []
      const laws = items.filter(i => i.uri && i.title)
      const lawMap = {}
      await Promise.all(laws.map(async (l) => {
        lawMap[l.uri] = { name: l.title, children: [] }
        try{
          const q = `PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nPREFIX lo: <http://legalontosystem.pe/ontology#>\nPREFIX dct: <http://purl.org/dc/terms/>\nSELECT ?art ?label ?titulo ?anio ?jurisd WHERE {\n  OPTIONAL {\n    { <${l.uri}> lo:tieneArticulo ?art } UNION { <${l.uri}> lo:hasArticle ?art } .\n    OPTIONAL { ?art rdfs:label ?label }\n  }\n  OPTIONAL { <${l.uri}> lo:titulo ?titulo }\n  OPTIONAL { <${l.uri}> lo:anio ?anio }\n  OPTIONAL { <${l.uri}> lo:aplicaEn ?jurisd }\n} LIMIT 500`;
          const r = await axios.post(`${API_BASE}/sparql`, { query: q })
          const rows = (r.data && r.data.results) || []
          rows.forEach(row => {
            const artUri = row.art || row['?art']
            const artLabel = row.label || row['?label'] || 'Artículo'
            if(artUri){
              lawMap[l.uri].children.push({ name: artLabel, uri: artUri })
            }
            if(row.titulo || row['?titulo']) lawMap[l.uri].title = row.titulo || row['?titulo']
            if(row.anio || row['?anio']) lawMap[l.uri].year = row.anio || row['?anio']
            if(row.jurisd || row['?jurisd']) lawMap[l.uri].jurisdiccion = row.jurisd || row['?jurisd']
          })
          // Deduplicate article children by uri
          if (lawMap[l.uri] && Array.isArray(lawMap[l.uri].children)){
            const seen = new Set()
            lawMap[l.uri].children = lawMap[l.uri].children.filter(c => {
              const key = c.uri || c.name
              if(!key) return false
              if(seen.has(key)) return false
              seen.add(key)
              return true
            })
          }
          if((lawMap[l.uri].children || []).length === 0){
            delete lawMap[l.uri]
          }
        }catch(e){
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
    <div className="fade-in">
      <Card className="mb-4">
        <Card.Header>
          <Card.Title className="mb-0">Jerarquía de Normas Legales</Card.Title>
          <small className="text-white-50">Visualiza la estructura de leyes, decretos y artículos en el ordenamiento jurídico</small>
        </Card.Header>
        <Card.Body>
          {loading && (
            <div className="text-center py-5">
              <Spinner animation="border" variant="primary" className="mb-3" />
              <p className="text-muted">Cargando estructura jerárquica...</p>
            </div>
          )}
          {hierarchyData && (
            <HierarchyTree data={hierarchyData} />
          )}
          {!loading && !hierarchyData && (
            <Alert variant="warning">
              No se pudieron cargar los datos jerárquicos. Intenta recargar la página.
            </Alert>
          )}
        </Card.Body>
      </Card>

      <Card className="mb-4">
        <Card.Header>
          <Card.Title className="mb-0">Estadísticas del Ordenamiento</Card.Title>
        </Card.Header>
        <Card.Body>
          {hierarchyData && (
            <>
              <Row className="mb-4">
                <Col sm={6} md={4}>
                  <div className="stat-box text-center p-4">
                    <div className="stat-label">Leyes Cargadas</div>
                    <div className="stat-value text-primary fw-bold">{hierarchyData.children?.length || 0}</div>
                  </div>
                </Col>
                <Col sm={6} md={4}>
                  <div className="stat-box text-center p-4">
                    <div className="stat-label">Artículos Totales</div>
                    <div className="stat-value text-primary fw-bold">
                      {hierarchyData.children?.reduce((sum, ley) => sum + (ley.children?.length || 0), 0) || 0}
                    </div>
                  </div>
                </Col>
              </Row>
              
              {hierarchyData.children && hierarchyData.children.length > 0 && (
                <div>
                  <h6 className="mb-3">Normas Cargadas (primeras 10)</h6>
                  <ul className="list-unstyled">
                    {hierarchyData.children.slice(0, 10).map((l, i) => (
                      <li key={i} className="py-2 border-bottom">
                        <strong className="text-primary">{l.name}</strong>
                        {l.year && <small className="ms-2 text-muted">Año: {String(l.year)}</small>}
                        {l.jurisdiccion && <small className="ms-2 text-muted">Jurisd: {String(l.jurisdiccion)}</small>}
                        {l.children && <small className="ms-2 badge bg-info">{l.children.length} artículos</small>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </Card.Body>
      </Card>
    </div>
  )
}

function HierarchyTree({data}){
  const width = 1600
  const height = 1200

  useEffect(() => {
    if(!data) return

    const svg = d3.select('.hierarchy-svg')
    svg.selectAll('*').remove()

    const viewport = svg.append('g').attr('class','viewport')
    const g = viewport.append('g')
      .attr('transform', `translate(${width/2},80)`)

    const zoom = d3.zoom()
      .scaleExtent([0.2, 4])
      .on('zoom', (event) => {
        viewport.attr('transform', event.transform)
      })
    svg.call(zoom)

    const tree = d3.tree()
      .size([width - 200, height - 200])
      .separation((a, b) => (a.parent === b.parent ? 2 : 3))
    
    const root = d3.hierarchy(data)
    const links = tree(root).links()
    const nodes = root.descendants()

    g.append('g')
      .attr('stroke', '#cbd5e1')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', 2.5)
      .selectAll('path')
      .data(links)
      .join('path')
      .attr('d', d3.linkVertical()
        .x(d => d.x)
        .y(d => d.y))

    const nodeG = g.append('g')
      .selectAll('g')
      .data(nodes)
      .join('g')
      .attr('transform', d => `translate(${d.x},${d.y})`)

    nodeG.append('circle')
      .attr('r', d => d.data.children ? 14 : 9)
      .attr('fill', d => d.data.children ? '#1a3a52' : '#4299e1')
      .attr('stroke', '#fff')
      .attr('stroke-width', 2.5)

    nodeG.append('text')
      .attr('x', d => d.data.children ? 0 : 0)
      .attr('y', d => d.data.children ? -28 : -18)
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .style('font-size', d => d.data.children ? '16px' : '14px')
      .style('font-weight', d => d.data.children ? 'bold' : '600')
      .style('fill', '#1a3a52')
      .style('pointer-events', 'none')
      .text(d => (d.data.name || 'N/A').substring(0, 50))
  }, [data])

  return (
    <div className="hierarchy-wrapper" style={{ overflowX: 'auto', overflowY: 'auto', width: '100%', height: '600px', border: '1px solid #e2e8f0', borderRadius: '0.375rem' }}>
      <svg className="hierarchy-svg" width={width} height={height} style={{ display: 'block' }}></svg>
    </div>
  )
}

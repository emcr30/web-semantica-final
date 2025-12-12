import React, { useRef, useEffect, useState } from 'react'
import * as d3 from 'd3'

export default function D3Graph({ nodes, links, width = 800, height = 600, onNodeClick }) {
  const ref = useRef()
  const wrapperRef = useRef()
  const svgRef = useRef()
  const [zoomLevel, setZoomLevel] = useState(1)
  const [selectedNode, setSelectedNode] = useState(null)
  const [size, setSize] = useState({ width: typeof width === 'number' ? width : 800, height: typeof height === 'number' ? height : 600 })

  // Auto-resize to container
  useEffect(() => {
    const el = wrapperRef.current
    if (!el) return
    const ro = new ResizeObserver(entries => {
      for (const entry of entries) {
        const cw = Math.max(300, Math.floor(entry.contentRect.width))
        const ch = Math.max(300, Math.floor(entry.contentRect.height))
        setSize({ width: cw, height: ch })
      }
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    const svg = d3.select(ref.current)
    svg.selectAll('*').remove()

    const w = size.width || (typeof width === 'number' ? width : 800)
    const h = size.height || (typeof height === 'number' ? height : 600)
    svg.attr('width', w).attr('height', h)

    if (!nodes || nodes.length === 0) {
      svg.append('text')
        .attr('x', w / 2)
        .attr('y', h / 2)
        .attr('text-anchor', 'middle')
        .attr('fill', '#94a3b8')
        .style('font-size', '16px')
        .style('font-weight', '500')
        .text('No hay datos para mostrar')
      return
    }

    // Definir gradientes y filtros para efectos visuales
    const defs = svg.append('defs')
    
    // Gradiente radial para nodos
    const gradient = defs.append('radialGradient')
      .attr('id', 'node-gradient')
    gradient.append('stop')
      .attr('offset', '0%')
      .attr('stop-color', '#60a5fa')
    gradient.append('stop')
      .attr('offset', '100%')
      .attr('stop-color', '#2563eb')

    // Gradiente para nodo seleccionado
    const gradientSelected = defs.append('radialGradient')
      .attr('id', 'node-gradient-selected')
    gradientSelected.append('stop')
      .attr('offset', '0%')
      .attr('stop-color', '#fbbf24')
    gradientSelected.append('stop')
      .attr('offset', '100%')
      .attr('stop-color', '#f59e0b')

    // Sombra para nodos
    const filter = defs.append('filter')
      .attr('id', 'shadow')
      .attr('x', '-50%')
      .attr('y', '-50%')
      .attr('width', '200%')
      .attr('height', '200%')
    filter.append('feGaussianBlur')
      .attr('in', 'SourceAlpha')
      .attr('stdDeviation', 3)
    filter.append('feOffset')
      .attr('dx', 0)
      .attr('dy', 2)
      .attr('result', 'offsetblur')
    filter.append('feComponentTransfer')
      .append('feFuncA')
      .attr('type', 'linear')
      .attr('slope', 0.3)
    const feMerge = filter.append('feMerge')
    feMerge.append('feMergeNode')
    feMerge.append('feMergeNode')
      .attr('in', 'SourceGraphic')

    // Marcador de flecha para enlaces direccionales
    defs.append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 25)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#94a3b8')

    const g = svg.append('g')

    const zoomHandler = d3.zoom()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
        setZoomLevel(event.transform.k)
      })

    svg.call(zoomHandler)

    // Simulación de fuerzas mejorada
    const sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(160).strength(0.6))
    .force('charge', d3.forceManyBody().strength(-260))
    .force('center', d3.forceCenter(w / 2, h / 2))
    .force('x', d3.forceX(w / 2).strength(0.05))
    .force('y', d3.forceY(h / 2).strength(0.05))
    .force('collision', d3.forceCollide().radius(70))
    .alphaDecay(0.15)        // Se estabiliza rápido
    // .velocityDecay(0.4);     // Reduce vibración


    // Enlaces con gradiente
    const linkGroup = g.append('g')
    const link = linkGroup
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', '#cbd5e1')
      .attr('stroke-opacity', 0.4)
      .attr('stroke-width', d => Math.sqrt(d.value || 1) * 1.5)
      .attr('marker-end', 'url(#arrowhead)')
      .style('transition', 'all 0.3s ease')

    // Grupo de nodos
    const nodeGroup = g.append('g')

    // Círculos exteriores (anillo decorativo)
    const nodeOuter = nodeGroup
      .selectAll('circle.outer')
      .data(nodes)
      .join('circle')
      .attr('class', 'outer')
      .attr('r', 18)
      .attr('fill', 'none')
      .attr('stroke', '#3b82f6')
      .attr('stroke-width', 2)
      .attr('stroke-opacity', 0.3)
      .style('pointer-events', 'none')

    // Nodos principales
    const node = nodeGroup
      .selectAll('circle.main')
      .data(nodes)
      .join('circle')
      .attr('class', 'main')
      .attr('r', 14)
      .attr('fill', 'url(#node-gradient)')
      .attr('stroke', '#fff')
      .attr('stroke-width', 2.5)
      .attr('filter', 'url(#shadow)')
      .style('cursor', 'pointer')
      .call(drag(sim))

    // Eventos de interacción mejorados
    node
      .on('click', (event, d) => {
        event.stopPropagation()
        setSelectedNode(d.id)
        if (onNodeClick) onNodeClick(d)
        
        // Destacar nodo y conexiones
        node.attr('fill', n => n.id === d.id ? 'url(#node-gradient-selected)' : 'url(#node-gradient)')
        node.attr('r', n => n.id === d.id ? 16 : 14)
        nodeOuter.attr('r', n => n.id === d.id ? 22 : 18)
        nodeOuter.attr('stroke-opacity', n => n.id === d.id ? 0.6 : 0.3)
        
        // Destacar enlaces conectados
        link.attr('stroke-opacity', l => 
          (l.source.id === d.id || l.target.id === d.id) ? 0.8 : 0.2
        )
        link.attr('stroke-width', l => 
          (l.source.id === d.id || l.target.id === d.id) 
            ? Math.sqrt(l.value || 1) * 2.5 
            : Math.sqrt(l.value || 1) * 1.5
        )
      })
      .on('mouseover', function(event, d) {
        if (selectedNode !== d.id) {
          d3.select(this)
            .transition()
            .duration(200)
            .attr('r', 16)
            .attr('stroke-width', 3)
          
          d3.select(this.parentNode)
            .selectAll('circle.outer')
            .filter(n => n.id === d.id)
            .transition()
            .duration(200)
            .attr('r', 22)
            .attr('stroke-opacity', 0.5)
        }
      })
      .on('mouseout', function(event, d) {
        if (selectedNode !== d.id) {
          d3.select(this)
            .transition()
            .duration(200)
            .attr('r', 14)
            .attr('stroke-width', 2.5)
          
          d3.select(this.parentNode)
            .selectAll('circle.outer')
            .filter(n => n.id === d.id)
            .transition()
            .duration(200)
            .attr('r', 18)
            .attr('stroke-opacity', 0.3)
        }
      })

    // Etiquetas con fondo semitransparente
    const labelGroup = g.append('g')
    
    const labelBg = labelGroup
      .selectAll('rect')
      .data(nodes)
      .join('rect')
      .attr('fill', 'rgba(255, 255, 255, 0.9)')
      .attr('stroke', '#e2e8f0')
      .attr('stroke-width', 1)
      .attr('rx', 4)
      .attr('ry', 4)
      .style('pointer-events', 'none')

    const label = labelGroup
      .selectAll('text')
      .data(nodes)
      .join('text')
      .text(d => d.label?.slice(0, 30) || d.id)
      .style('font-size', '12px')
      .style('font-weight', '600')
      .style('fill', '#1e293b')
      .style('pointer-events', 'none')
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'middle')

    // Calcular tamaño de fondo de texto
    label.each(function(d) {
      const bbox = this.getBBox()
      d.labelWidth = bbox.width + 12
      d.labelHeight = bbox.height + 6
    })

    sim.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y)

      node
        .attr('cx', d => d.x)
        .attr('cy', d => d.y)

      nodeOuter
        .attr('cx', d => d.x)
        .attr('cy', d => d.y)

      label
        .attr('x', d => d.x)
        .attr('y', d => d.y + 30)

      labelBg
        .attr('x', d => d.x - d.labelWidth / 2)
        .attr('y', d => d.y + 30 - d.labelHeight / 2)
        .attr('width', d => d.labelWidth)
        .attr('height', d => d.labelHeight)
    })

    svgRef.current = { svg, zoomHandler, g }
    return () => sim.stop()
  }, [nodes, links, size.width, size.height, selectedNode])

  function resetZoom() {
    if (svgRef.current) {
      svgRef.current.svg
        .transition()
        .duration(750)
        .call(svgRef.current.zoomHandler.transform, d3.zoomIdentity)
      setZoomLevel(1)
      setSelectedNode(null)
    }
  }

  function drag(simulation) {
    function dragstarted(event) {
      if (!event.active) simulation.alphaTarget(0.3).restart()
      event.subject.fx = event.subject.x
      event.subject.fy = event.subject.y
    }
    function dragged(event) {
      event.subject.fx = event.x
      event.subject.fy = event.y
    }
    function dragended(event) {
      if (!event.active) simulation.alphaTarget(0)
      event.subject.fx = null
      event.subject.fy = null
    }
    return d3.drag()
      .on('start', dragstarted)
      .on('drag', dragged)
      .on('end', dragended)
  }

  return (
    <div ref={wrapperRef} style={{
      width: '100%',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      backgroundColor: '#f8fafc',
      borderRadius: '12px',
      overflow: 'hidden',
      boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
    }}>
      <div style={{
        padding: '16px 20px',
        backgroundColor: '#fff',
        borderBottom: '1px solid #e2e8f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '12px'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <button
            onClick={resetZoom}
            style={{
              padding: '8px 16px',
              backgroundColor: '#3b82f6',
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              fontSize: '14px',
              fontWeight: '600',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.2s',
              boxShadow: '0 1px 3px rgba(0, 0, 0, 0.12)'
            }}
            onMouseOver={e => e.target.style.backgroundColor = '#2563eb'}
            onMouseOut={e => e.target.style.backgroundColor = '#3b82f6'}
          >
            <span>🔍</span>
            <span>Reset</span>
          </button>
          <div style={{
            padding: '6px 12px',
            backgroundColor: '#f1f5f9',
            borderRadius: '6px',
            fontSize: '13px',
            fontWeight: '600',
            color: '#475569'
          }}>
            Zoom: {zoomLevel.toFixed(2)}x
          </div>
        </div>
        <div style={{
          fontSize: '13px',
          color: '#64748b',
          display: 'flex',
          gap: '16px'
        }}>
        </div>
      </div>
      <svg
        ref={ref}
        width={size.width}
        height={size.height}
        style={{
          flex: 1,
          backgroundColor: '#ffffff',
          backgroundImage: `
            radial-gradient(circle, #e2e8f0 1px, transparent 1px)
          `,
          backgroundSize: '20px 20px'
        }}
      />
    </div>
  )
}
import React, {useRef, useEffect} from 'react'
import * as d3 from 'd3'

export default function D3Graph({nodes, links, width=800, height=600, onNodeClick}){
  const ref = useRef()

  useEffect(()=>{
    const svg = d3.select(ref.current)
    svg.selectAll('*').remove()
    if(!nodes || nodes.length===0){
      svg.append('text')
        .attr('x',width/2)
        .attr('y',height/2)
        .attr('text-anchor','middle')
        .attr('fill','#94a3b8')
        .style('font-size','14px')
        .text('No hay datos para mostrar')
      return
    }

    const sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d=>d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width/2, height/2))

    const link = svg.append('g')
      .attr('stroke', '#cbd5e1')
      .attr('stroke-opacity', 0.6)
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke-width', 2)

    const node = svg.append('g')
      .selectAll('circle')
      .data(nodes)
      .join('circle')
      .attr('r', 10)
      .attr('fill', '#1e40af')
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .style('cursor', 'pointer')
      .call(drag(sim))
      .on('click', (event, d)=>{
        if(onNodeClick) onNodeClick(d)
      })
      .on('mouseover', function() {
        d3.select(this).attr('fill', '#3b82f6').attr('r', 12)
      })
      .on('mouseout', function() {
        d3.select(this).attr('fill', '#1e40af').attr('r', 10)
      })

    const label = svg.append('g')
      .selectAll('text')
      .data(nodes)
      .join('text')
      .attr('x',15)
      .attr('y',4)
      .text(d=>d.label?.slice(0,50) || d.id)
      .style('font-size','11px')
      .style('fill','#334155')
      .style('pointer-events', 'none')

    sim.on('tick', ()=>{
      link
        .attr('x1', d=>d.source.x)
        .attr('y1', d=>d.source.y)
        .attr('x2', d=>d.target.x)
        .attr('y2', d=>d.target.y)

      node
        .attr('cx', d=>d.x)
        .attr('cy', d=>d.y)

      label
        .attr('x', d=>d.x)
        .attr('y', d=>d.y)
    })

    return ()=> sim.stop()
  }, [nodes, links, width, height])

  function drag(simulation){
    function dragstarted(event){
      if(!event.active) simulation.alphaTarget(0.3).restart()
      event.subject.fx = event.subject.x
      event.subject.fy = event.subject.y
    }
    function dragged(event){
      event.subject.fx = event.x
      event.subject.fy = event.y
    }
    function dragended(event){
      if(!event.active) simulation.alphaTarget(0)
      event.subject.fx = null
      event.subject.fy = null
    }
    return d3.drag()
      .on('start', dragstarted)
      .on('drag', dragged)
      .on('end', dragended)
  }

  return <svg ref={ref} width={width} height={height} className="graph-svg" />
}
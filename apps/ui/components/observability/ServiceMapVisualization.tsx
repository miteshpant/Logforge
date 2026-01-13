'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import * as d3 from 'd3'
import type { ServiceNode, ServiceEdge, ServiceMapData } from '@/app/observability/service-map/page'

interface ServiceMapVisualizationProps {
  data: ServiceMapData | null
  isLoading: boolean
  selectedNode: ServiceNode | null
  onNodeSelect: (node: ServiceNode | null) => void
}

interface D3Node extends ServiceNode, d3.SimulationNodeDatum {}
interface D3Link extends ServiceEdge, d3.SimulationLinkDatum<D3Node> {}

export default function ServiceMapVisualization({
  data,
  isLoading,
  selectedNode,
  onNodeSelect
}: ServiceMapVisualizationProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 })

  // Store onNodeSelect in a ref to avoid re-renders
  const onNodeSelectRef = useRef(onNodeSelect)
  onNodeSelectRef.current = onNodeSelect

  // Update dimensions on mount and resize
  useEffect(() => {
    const updateDimensions = () => {
      if (svgRef.current) {
        const rect = svgRef.current.parentElement?.getBoundingClientRect()
        if (rect && rect.width > 0) {
          setDimensions({
            width: rect.width,
            height: Math.max(600, rect.height)
          })
        }
      }
    }

    // Initial update with small delay to ensure DOM is ready
    const timeoutId = setTimeout(updateDimensions, 100)

    // Use ResizeObserver for reliable dimension detection
    const resizeObserver = new ResizeObserver(() => {
      updateDimensions()
    })

    if (svgRef.current?.parentElement) {
      resizeObserver.observe(svgRef.current.parentElement)
    }

    window.addEventListener('resize', updateDimensions)

    return () => {
      clearTimeout(timeoutId)
      resizeObserver.disconnect()
      window.removeEventListener('resize', updateDimensions)
    }
  }, [])

  // Re-check dimensions when data loads (container may resize after loading state changes)
  useEffect(() => {
    if (data && svgRef.current) {
      const rect = svgRef.current.parentElement?.getBoundingClientRect()
      if (rect && rect.width > 0 && dimensions.width === 0) {
        setDimensions({
          width: rect.width,
          height: Math.max(600, rect.height)
        })
      }
    }
  }, [data, dimensions.width])

  // Render D3 visualization - only when data or dimensions change
  useEffect(() => {
    if (!data || !svgRef.current || dimensions.width === 0) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove() // Clear previous render

    const { width, height } = dimensions

    // Create container group for zoom/pan
    const container = svg
      .append('g')
      .attr('class', 'container')

    // Setup zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.5, 3])
      .on('zoom', (event) => {
        container.attr('transform', event.transform)
      })

    svg.call(zoom)

    // Prepare data
    const nodes: D3Node[] = data.nodes.map(node => ({ ...node }))
    const links: D3Link[] = data.edges.map(edge => ({
      ...edge,
      source: edge.source,
      target: edge.target
    }))

    // Create force simulation with tighter spacing
    const simulation = d3.forceSimulation<D3Node>(nodes)
      .force('link', d3.forceLink<D3Node, D3Link>(links)
        .id(d => d.id)
        .distance(80))  // Reduced from 150 - brings linked nodes closer
      .force('charge', d3.forceManyBody().strength(-200))  // Reduced from -400 - less repulsion
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(35))  // Reduced from 50 - allows nodes to be closer

    // Create arrow markers for directed edges
    const defs = container.append('defs')

    // Define arrow markers for each health status (matching DB enum: healthy, degraded, unhealthy, unknown)
    const healthColors: Record<string, string> = {
      healthy: '#10b981',   // emerald-500
      degraded: '#eab308',  // yellow-500
      unhealthy: '#ef4444', // red-500
      unknown: '#94a3b8',   // slate-400
      down: '#ef4444'       // legacy support
    }

    Object.entries(healthColors).forEach(([status, color]) => {
      defs.append('marker')
        .attr('id', `arrow-${status}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 25)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', color)
        .attr('opacity', 0.6)
    })

    // Create links
    const link = container.append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', '#475569')
      .attr('stroke-width', d => Math.min(8, Math.max(1, d.metrics.request_count / 1000)))
      .attr('stroke-opacity', 0.6)
      .attr('marker-end', 'url(#arrow-healthy)')

    // Add link labels for request counts
    const linkLabels = container.append('g')
      .attr('class', 'link-labels')
      .selectAll('text')
      .data(links)
      .join('text')
      .attr('font-size', '10px')
      .attr('fill', '#94a3b8')
      .attr('text-anchor', 'middle')
      .text(d => {
        const count = d.metrics.request_count
        if (count >= 1000) return `${(count / 1000).toFixed(1)}k`
        return count.toString()
      })

    // Create node groups
    const node = container.append('g')
      .attr('class', 'nodes')
      .selectAll('g')
      .data(nodes)
      .join('g')
      .attr('class', 'node')
      .attr('data-node-id', d => d.id)
      .style('cursor', 'pointer')
      .call(d3.drag<SVGGElement, D3Node>()
        .on('start', dragStarted)
        .on('drag', dragged)
        .on('end', dragEnded))
      .on('click', (event, d) => {
        event.stopPropagation()
        onNodeSelectRef.current(d)
      })

    // Add node circles
    const getNodeColor = (node: ServiceNode) => {
      // Type colors matching DB enum: api, application, database, cache, queue, external
      const typeColors: Record<string, string> = {
        api: '#06b6d4',         // cyan-500
        application: '#3b82f6', // blue-500
        service: '#3b82f6',     // blue-500 (legacy)
        database: '#a855f7',    // purple-500
        cache: '#f97316',       // orange-500
        queue: '#ec4899',       // pink-500
        external: '#64748b'     // slate-500
      }
      return typeColors[node.type] || '#64748b'
    }

    const getHealthColor = (health: string) => healthColors[health] || healthColors.unknown

    node.append('circle')
      .attr('r', 20)
      .attr('fill', d => getNodeColor(d))
      .attr('stroke', d => getHealthColor(d.health))
      .attr('stroke-width', 3)
      .attr('class', 'node-circle')

    // Add node icons (first letter of name)
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.3em')
      .attr('font-size', '14px')
      .attr('font-weight', 'bold')
      .attr('fill', '#ffffff')
      .attr('pointer-events', 'none')
      .text(d => d.name.charAt(0).toUpperCase())

    // Add node labels
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '35px')
      .attr('font-size', '12px')
      .attr('fill', '#e2e8f0')
      .attr('pointer-events', 'none')
      .text(d => d.name)

    // Add error indicator for non-healthy services (degraded, unhealthy, unknown)
    node.filter(d => d.health !== 'healthy')
      .append('circle')
      .attr('r', 6)
      .attr('cx', 15)
      .attr('cy', -15)
      .attr('fill', d => getHealthColor(d.health))
      .attr('stroke', '#1e293b')
      .attr('stroke-width', 2)

    // Update positions on simulation tick
    simulation.on('tick', () => {
      link
        .attr('x1', d => (d.source as D3Node).x!)
        .attr('y1', d => (d.source as D3Node).y!)
        .attr('x2', d => (d.target as D3Node).x!)
        .attr('y2', d => (d.target as D3Node).y!)

      linkLabels
        .attr('x', d => ((d.source as D3Node).x! + (d.target as D3Node).x!) / 2)
        .attr('y', d => ((d.source as D3Node).y! + (d.target as D3Node).y!) / 2)

      node.attr('transform', d => `translate(${d.x},${d.y})`)
    })

    // Drag functions
    function dragStarted(event: d3.D3DragEvent<SVGGElement, D3Node, D3Node>) {
      if (!event.active) simulation.alphaTarget(0.3).restart()
      event.subject.fx = event.subject.x
      event.subject.fy = event.subject.y
    }

    function dragged(event: d3.D3DragEvent<SVGGElement, D3Node, D3Node>) {
      event.subject.fx = event.x
      event.subject.fy = event.y
    }

    function dragEnded(event: d3.D3DragEvent<SVGGElement, D3Node, D3Node>) {
      if (!event.active) simulation.alphaTarget(0)
      event.subject.fx = null
      event.subject.fy = null
    }

    // Click on background to deselect
    svg.on('click', () => {
      onNodeSelectRef.current(null)
    })

    // Cleanup
    return () => {
      simulation.stop()
    }
  }, [data, dimensions]) // Removed selectedNode and onNodeSelect from dependencies

  // Separate effect for handling selection highlighting (doesn't rebuild visualization)
  useEffect(() => {
    if (!svgRef.current) return

    const svg = d3.select(svgRef.current)

    // Reset all nodes to default style
    svg.selectAll('.node .node-circle')
      .attr('stroke-width', 3)
      .style('filter', null)

    // Highlight selected node
    if (selectedNode) {
      svg.select(`.node[data-node-id="${selectedNode.id}"] .node-circle`)
        .attr('stroke-width', 5)
        .style('filter', 'drop-shadow(0 0 8px rgba(59, 130, 246, 0.5))')
    }
  }, [selectedNode])

  if (isLoading) {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6 h-[600px] flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-slate-600 border-t-blue-500 mb-4"></div>
          <p className="text-slate-400">Loading service map...</p>
        </div>
      </div>
    )
  }

  if (!data || data.nodes.length === 0) {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6 h-[600px] flex items-center justify-center">
        <div className="text-center">
          <p className="text-slate-400 mb-2">No services found</p>
          <p className="text-slate-500 text-sm">Start sending traces to see your service map</p>
        </div>
      </div>
    )
  }

  return (
    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5">
      {/* Instructions */}
      <div className="absolute top-4 left-4 z-10 bg-slate-900/80 backdrop-blur-sm rounded-lg px-3 py-2 text-xs text-slate-400">
        <p>Drag nodes to reposition • Scroll to zoom • Click nodes for details</p>
      </div>

      {/* SVG Container */}
      <svg
        ref={svgRef}
        width="100%"
        height={dimensions.height || 600}
        className="bg-slate-900/50"
      />

      {/* Stats */}
      <div className="absolute bottom-4 left-4 z-10 bg-slate-900/80 backdrop-blur-sm rounded-lg px-3 py-2 text-xs text-slate-400">
        <p>{data.nodes.length} services • {data.edges.length} connections</p>
      </div>
    </div>
  )
}

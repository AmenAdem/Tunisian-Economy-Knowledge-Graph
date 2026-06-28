import React, { useEffect, useRef, useState } from 'react'
import cytoscape from 'cytoscape'
import fcose from 'cytoscape-fcose'
import axios from 'axios'
import './GraphVisualization.css'

// Register layout
cytoscape.use(fcose)

const GraphVisualizationV2 = () => {
  const containerRef = useRef(null)
  const cyRef = useRef(null)
  const [loading, setLoading] = useState(false)
  const [entityInfo, setEntityInfo] = useState(null)
  const [viewMode, setViewMode] = useState('overview') // overview, entity, type
  const [stats, setStats] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [entityTypes] = useState(['Person', 'Company', 'Group', 'Bank', 'Organization'])

  useEffect(() => {
    if (!containerRef.current) return

    // Initialize Cytoscape with enhanced styles
    cyRef.current = cytoscape({
      container: containerRef.current,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': '#3498db',
            label: 'data(label)',
            'text-valign': 'center',
            'text-halign': 'center',
            'font-size': '11px',
            'font-weight': 'bold',
            color: '#2c3e50',
            'text-outline-width': 2,
            'text-outline-color': '#fff',
            'text-wrap': 'wrap',
            'text-max-width': '80px',
            width: '50px',
            height: '50px',
            'border-width': 2,
            'border-color': '#2c3e50',
          },
        },
        {
          selector: 'node[type="Person"]',
          style: {
            'background-color': '#e74c3c',
            shape: 'ellipse',
          },
        },
        {
          selector: 'node[type="Company"]',
          style: {
            'background-color': '#3498db',
            shape: 'roundrectangle',
          },
        },
        {
          selector: 'node[type="Group"]',
          style: {
            'background-color': '#9b59b6',
            shape: 'diamond',
            width: '70px',
            height: '70px',
          },
        },
        {
          selector: 'node[type="Bank"]',
          style: {
            'background-color': '#2ecc71',
            shape: 'hexagon',
          },
        },
        {
          selector: 'node[type="Organization"]',
          style: {
            'background-color': '#f39c12',
            shape: 'triangle',
          },
        },
        {
          selector: 'node[type="Sector"]',
          style: {
            'background-color': '#1abc9c',
            shape: 'star',
          },
        },
        {
          selector: 'node[type="Location"]',
          style: {
            'background-color': '#34495e',
            shape: 'octagon',
          },
        },
        {
          selector: 'edge',
          style: {
            width: 2,
            'line-color': '#95a5a6',
            'target-arrow-color': '#95a5a6',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            label: 'data(label)',
            'font-size': '9px',
            color: '#7f8c8d',
            'text-rotation': 'autorotate',
            'text-background-color': '#fff',
            'text-background-opacity': 0.8,
            'text-background-padding': '2px',
          },
        },
        {
          selector: 'edge[relation="OWNS"]',
          style: {
            'line-color': '#e74c3c',
            'target-arrow-color': '#e74c3c',
            width: 3,
          },
        },
        {
          selector: 'edge[relation="DIRECTOR_OF"]',
          style: {
            'line-color': '#f39c12',
            'target-arrow-color': '#f39c12',
            width: 3,
          },
        },
        {
          selector: 'edge[relation="SUBSIDIARY_OF"]',
          style: {
            'line-color': '#3498db',
            'target-arrow-color': '#3498db',
            'line-style': 'dashed',
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 5,
            'border-color': '#f39c12',
            'overlay-color': '#f39c12',
            'overlay-opacity': 0.3,
            'overlay-padding': 5,
          },
        },
        {
          selector: 'node:active',
          style: {
            'overlay-color': '#2ecc71',
            'overlay-opacity': 0.3,
          },
        },
      ],
      layout: {
        name: 'fcose',
        quality: 'proof',
        randomize: false,
        animate: true,
        animationDuration: 1000,
        nodeSeparation: 150,         // Increased spacing
        idealEdgeLength: 150,        // Longer edges
        edgeElasticity: 0.45,
        nestingFactor: 0.1,
        gravity: 0.25,               // Reduced gravity for spread
        numIter: 2500,
        tile: true,
        tilingPaddingVertical: 20,   // More padding
        tilingPaddingHorizontal: 20,
        packComponents: true,        // Pack components nicely
      },
      wheelSensitivity: 0.2,         // Smooth zoom
      minZoom: 0.1,
      maxZoom: 3,
    })

    // Click handler
    cyRef.current.on('tap', 'node', (evt) => {
      const node = evt.target
      loadEntityDetails(node.data('id'))
      // Highlight neighbors
      const neighborhood = node.neighborhood().add(node)
      cyRef.current.elements().removeClass('faded')
      cyRef.current.elements().not(neighborhood).addClass('faded')
    })

    // Tap on background to clear selection
    cyRef.current.on('tap', (evt) => {
      if (evt.target === cyRef.current) {
        cyRef.current.elements().removeClass('faded')
        setEntityInfo(null)
      }
    })

    // Add fade style
    cyRef.current.style().selector('.faded').style({
      opacity: 0.25,
    }).update()

    // Load initial graph
    loadGraphOverview()

    return () => {
      if (cyRef.current) {
        cyRef.current.destroy()
      }
    }
  }, [])

  const loadGraphOverview = async (limit = 100) => {
    setLoading(true)
    try {
      const res = await axios.get(`/api/graph/explore/overview?limit=${limit}&min_confidence=0.6`)
      const data = res.data

      updateGraph(data.nodes, data.edges)
      setStats(data.stats)
      setViewMode('overview')
    } catch (error) {
      console.error('Failed to load graph overview:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadEntityNeighborhood = async (entityName, depth = 2) => {
    setLoading(true)
    try {
      const res = await axios.get(
        `/api/graph/explore/entity/${encodeURIComponent(entityName)}/neighborhood?depth=${depth}&limit=50`
      )
      const data = res.data

      updateGraph(data.nodes, data.edges)
      setStats(data.stats)
      setViewMode('entity')
    } catch (error) {
      console.error('Failed to load entity neighborhood:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadGraphByType = async (entityType) => {
    setLoading(true)
    try {
      const res = await axios.get(`/api/graph/explore/by-type/${entityType}?limit=50`)
      const data = res.data

      updateGraph(data.nodes, data.edges)
      setStats(data.stats)
      setViewMode('type')
    } catch (error) {
      console.error('Failed to load graph by type:', error)
    } finally {
      setLoading(false)
    }
  }

  const updateGraph = (nodes, edges) => {
    if (!cyRef.current) return

    // Convert to Cytoscape format
    const elements = []

    // Add nodes
    nodes.forEach((node) => {
      elements.push({
        data: {
          id: node.id,
          label: node.label,
          type: node.type,
          confidence: node.confidence,
        },
      })
    })

    // Add edges
    edges.forEach((edge) => {
      elements.push({
        data: {
          source: edge.source,
          target: edge.target,
          label: edge.relation,
          relation: edge.relation,
          confidence: edge.confidence,
        },
      })
    })

    // Update graph
    cyRef.current.elements().remove()
    cyRef.current.add(elements)
    cyRef.current
      .layout({
        name: 'fcose',
        quality: 'proof',
        randomize: false,
        animate: true,
        animationDuration: 1000,
        nodeSeparation: 100,
        idealEdgeLength: 100,
      })
      .run()
  }

  const loadEntityDetails = async (entityName) => {
    try {
      const res = await axios.get(`/api/entities/${encodeURIComponent(entityName)}`)
      setEntityInfo(res.data)
    } catch (error) {
      console.error('Failed to load entity details:', error)
    }
  }

  const handleSearch = async (e) => {
    e.preventDefault()
    if (!searchQuery || searchQuery.length < 2) return

    try {
      const res = await axios.get(`/api/entities/search?q=${encodeURIComponent(searchQuery)}&limit=10`)
      setSearchResults(res.data)
    } catch (error) {
      console.error('Search failed:', error)
    }
  }

  const selectEntity = (entityName) => {
    loadEntityNeighborhood(entityName)
    setSearchQuery('')
    setSearchResults([])
  }

  return (
    <div className="graph-container-v2">
      <div className="graph-controls">
        <div className="control-section">
          <h4>View Mode</h4>
          <button onClick={() => loadGraphOverview(50)} className="btn-control">
            Quick View (50)
          </button>
          <button onClick={() => loadGraphOverview(100)} className="btn-control">
            Standard (100)
          </button>
          <button onClick={() => loadGraphOverview(200)} className="btn-control">
            Extended (200)
          </button>
          <button onClick={() => loadGraphOverview(500)} className="btn-control">
            Full Graph (500)
          </button>
        </div>

        <div className="control-section">
          <h4>Layout Controls</h4>
          <button onClick={() => {
            if (cyRef.current) {
              cyRef.current.fit(50)
            }
          }} className="btn-control btn-small">
            🔍 Fit to Screen
          </button>
          <button onClick={() => {
            if (cyRef.current) {
              cyRef.current.center()
            }
          }} className="btn-control btn-small">
            📍 Center
          </button>
          <button onClick={() => {
            if (cyRef.current) {
              cyRef.current.layout({
                name: 'fcose',
                animate: true,
                nodeSeparation: 150,
                idealEdgeLength: 150,
              }).run()
            }
          }} className="btn-control btn-small">
            🔄 Re-layout
          </button>
        </div>

        <div className="control-section">
          <h4>By Entity Type</h4>
          {entityTypes.map((type) => (
            <button key={type} onClick={() => loadGraphByType(type)} className="btn-control btn-small">
              {type}
            </button>
          ))}
        </div>

        <div className="control-section">
          <h4>Search Entity</h4>
          <form onSubmit={handleSearch}>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search..."
              className="search-input"
            />
            <button type="submit" className="btn-search">
              Search
            </button>
          </form>
          {searchResults.length > 0 && (
            <div className="search-results">
              {searchResults.map((result, idx) => (
                <div key={idx} className="search-result-item" onClick={() => selectEntity(result.name)}>
                  <strong>{result.name}</strong>
                  <span className="result-type">{result.type}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {stats && (
          <div className="control-section stats">
            <h4>Graph Stats</h4>
            <p>Nodes: {stats.total_nodes}</p>
            <p>Edges: {stats.total_edges}</p>
            {stats.center_entity && <p>Center: {stats.center_entity}</p>}
            {stats.min_confidence && <p>Min Confidence: {(stats.min_confidence * 100).toFixed(0)}%</p>}
          </div>
        )}
      </div>

      <div className="graph-canvas" ref={containerRef} />

      {loading && (
        <div className="loading-overlay">
          <div className="spinner"></div>
          <p>Loading graph...</p>
        </div>
      )}

      {entityInfo && (
        <div className="entity-info-panel">
          <button className="close-btn" onClick={() => setEntityInfo(null)}>
            ×
          </button>
          <h3>{entityInfo.name}</h3>
          <p className="entity-type-badge">{entityInfo.type}</p>

          {entityInfo.aliases && entityInfo.aliases.length > 0 && (
            <div className="info-section">
              <strong>Also known as:</strong>
              <ul className="aliases-list">
                {entityInfo.aliases.map((alias, i) => (
                  <li key={i}>{alias}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="info-section">
            <strong>Confidence:</strong>
            <div className="confidence-bar">
              <div className="confidence-fill" style={{ width: `${entityInfo.confidence * 100}%` }}></div>
            </div>
            <span>{(entityInfo.confidence * 100).toFixed(0)}%</span>
          </div>

          {entityInfo.documents && entityInfo.documents.length > 0 && (
            <div className="info-section">
              <strong>Mentioned in:</strong>
              <p>{entityInfo.documents.length} document(s)</p>
            </div>
          )}

          <button className="btn-explore" onClick={() => loadEntityNeighborhood(entityInfo.name, 2)}>
            Explore Connections
          </button>
        </div>
      )}
    </div>
  )
}

export default GraphVisualizationV2

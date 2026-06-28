import React, { useEffect, useRef, useState } from 'react'
import cytoscape from 'cytoscape'
import fcose from 'cytoscape-fcose'
import axios from 'axios'
import './GraphVisualization.css'

// Register layout
cytoscape.use(fcose)

const GraphVisualization = ({ selectedEntity }) => {
  const containerRef = useRef(null)
  const cyRef = useRef(null)
  const [loading, setLoading] = useState(false)
  const [entityInfo, setEntityInfo] = useState(null)

  useEffect(() => {
    if (!containerRef.current) return

    // Initialize Cytoscape
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
            'font-size': '12px',
            color: '#2c3e50',
            'text-outline-width': 2,
            'text-outline-color': '#fff',
            width: '60px',
            height: '60px',
          },
        },
        {
          selector: 'node[type="Person"]',
          style: {
            'background-color': '#e74c3c',
          },
        },
        {
          selector: 'node[type="Company"]',
          style: {
            'background-color': '#3498db',
          },
        },
        {
          selector: 'node[type="Group"]',
          style: {
            'background-color': '#9b59b6',
            width: '80px',
            height: '80px',
          },
        },
        {
          selector: 'node[type="Bank"]',
          style: {
            'background-color': '#2ecc71',
          },
        },
        {
          selector: 'edge',
          style: {
            width: 3,
            'line-color': '#95a5a6',
            'target-arrow-color': '#95a5a6',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            label: 'data(label)',
            'font-size': '10px',
            color: '#7f8c8d',
            'text-rotation': 'autorotate',
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 4,
            'border-color': '#f39c12',
          },
        },
      ],
      layout: {
        name: 'fcose',
        quality: 'proof',
        randomize: false,
        animate: true,
        animationDuration: 500,
      },
    })

    // Click handler
    cyRef.current.on('tap', 'node', (evt) => {
      const node = evt.target
      loadEntityDetails(node.data('id'))
    })

    return () => {
      if (cyRef.current) {
        cyRef.current.destroy()
      }
    }
  }, [])

  useEffect(() => {
    if (selectedEntity) {
      loadEntityGraph(selectedEntity)
    }
  }, [selectedEntity])

  const loadEntityGraph = async (entityName) => {
    setLoading(true)
    try {
      // Get entity details
      const entityRes = await axios.get(`/api/entities/${entityName}`)
      const entity = entityRes.data

      // Get relationships
      const relRes = await axios.get(`/api/entities/${entityName}/relationships`)
      const relationships = relRes.data

      // Build graph elements
      const elements = []

      // Add central entity
      elements.push({
        data: {
          id: entity.name,
          label: entity.name,
          type: entity.type,
        },
      })

      // Add related entities and edges
      relationships.forEach((rel) => {
        if (rel.target_name) {
          // Outgoing relationship
          elements.push({
            data: {
              id: rel.target_name,
              label: rel.target_name,
              type: rel.target_type,
            },
          })
          elements.push({
            data: {
              source: entity.name,
              target: rel.target_name,
              label: rel.relation_type,
            },
          })
        } else if (rel.source_name) {
          // Incoming relationship
          elements.push({
            data: {
              id: rel.source_name,
              label: rel.source_name,
              type: rel.source_type,
            },
          })
          elements.push({
            data: {
              source: rel.source_name,
              target: entity.name,
              label: rel.relation_type,
            },
          })
        }
      })

      // Update graph
      if (cyRef.current) {
        cyRef.current.elements().remove()
        cyRef.current.add(elements)
        cyRef.current.layout({ name: 'fcose' }).run()
      }

      setEntityInfo(entity)
    } catch (error) {
      console.error('Failed to load entity graph:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadEntityDetails = async (entityName) => {
    try {
      const res = await axios.get(`/api/entities/${entityName}`)
      setEntityInfo(res.data)
    } catch (error) {
      console.error('Failed to load entity details:', error)
    }
  }

  return (
    <div className="graph-container">
      <div className="graph-canvas" ref={containerRef} />
      {loading && <div className="loading-overlay">Loading...</div>}
      {entityInfo && (
        <div className="entity-info-panel">
          <h3>{entityInfo.name}</h3>
          <p className="entity-type">{entityInfo.type}</p>
          {entityInfo.aliases && entityInfo.aliases.length > 0 && (
            <div>
              <strong>Aliases:</strong>
              <ul>
                {entityInfo.aliases.map((alias, i) => (
                  <li key={i}>{alias}</li>
                ))}
              </ul>
            </div>
          )}
          <p>
            <strong>Confidence:</strong> {(entityInfo.confidence * 100).toFixed(0)}%
          </p>
          {entityInfo.documents && entityInfo.documents.length > 0 && (
            <div>
              <strong>Sources:</strong> {entityInfo.documents.length} documents
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default GraphVisualization

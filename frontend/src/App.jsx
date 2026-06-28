import React, { useState } from 'react'
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom'
import GraphVisualizationV2 from './components/GraphVisualizationV2'
import './components/GraphVisualizationV2.css'
import DocumentUpload from './components/DocumentUpload'
import './App.css'

function App() {
  return (
    <Router>
      <div className="app">
        <header className="app-header">
          <h1>🇹🇳 Tunisian Economy Knowledge Graph</h1>
          <nav>
            <Link to="/">Graph Explorer</Link>
            <Link to="/upload">Upload Documents</Link>
          </nav>
        </header>

        <Routes>
          <Route path="/" element={<GraphVisualizationV2 />} />
          <Route path="/upload" element={<DocumentUpload />} />
        </Routes>
      </div>
    </Router>
  )
}

export default App

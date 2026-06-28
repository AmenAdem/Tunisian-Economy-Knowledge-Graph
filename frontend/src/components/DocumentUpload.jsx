import React, { useState } from 'react'
import axios from 'axios'
import './DocumentUpload.css'

const DocumentUpload = () => {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleFileChange = (e) => {
    setFile(e.target.files[0])
    setResult(null)
    setError(null)
  }

  const handleUpload = async (e) => {
    e.preventDefault()
    if (!file) return

    setUploading(true)
    setError(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await axios.post('/api/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult(res.data)
      setFile(null)
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="upload-container">
      <h2>Upload PDF Document</h2>
      <p>Upload business documents to extract entities and relationships.</p>

      <form onSubmit={handleUpload} className="upload-form">
        <input
          type="file"
          accept=".pdf"
          onChange={handleFileChange}
          className="file-input"
        />
        <button
          type="submit"
          disabled={!file || uploading}
          className="upload-button"
        >
          {uploading ? 'Processing...' : 'Upload & Extract'}
        </button>
      </form>

      {error && <div className="error-message">{error}</div>}

      {result && (
        <div className="result-card">
          <h3>Processing Complete</h3>
          <div className="result-stats">
            <div className="stat">
              <strong>{result.pages}</strong>
              <span>Pages</span>
            </div>
            <div className="stat">
              <strong>{result.chunks}</strong>
              <span>Chunks</span>
            </div>
            <div className="stat">
              <strong>{result.entities_extracted}</strong>
              <span>Entities</span>
            </div>
            <div className="stat">
              <strong>{result.relations_extracted}</strong>
              <span>Relations</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default DocumentUpload

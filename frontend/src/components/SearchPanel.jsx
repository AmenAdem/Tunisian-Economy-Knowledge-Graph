import React, { useState } from 'react'
import axios from 'axios'
import './SearchPanel.css'

const SearchPanel = ({ onSelectEntity }) => {
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [naturalLanguageQuery, setNaturalLanguageQuery] = useState('')
  const [nlResults, setNlResults] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleSearch = async (e) => {
    e.preventDefault()
    if (!query.trim()) return

    setLoading(true)
    try {
      const res = await axios.get(`/api/entities/search`, {
        params: { q: query, limit: 20 },
      })
      setSearchResults(res.data)
    } catch (error) {
      console.error('Search failed:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleNaturalLanguageQuery = async (e) => {
    e.preventDefault()
    if (!naturalLanguageQuery.trim()) return

    setLoading(true)
    try {
      const res = await axios.post(`/api/query/ask`, {
        question: naturalLanguageQuery,
      })
      setNlResults(res.data)
    } catch (error) {
      console.error('Query failed:', error)
      setNlResults({ error: 'Failed to process question' })
    } finally {
      setLoading(false)
    }
  }

  const exampleQuestions = [
    'Who owns Poulina Group?',
    'What companies are linked to Abdelwaheb Ben Ayed?',
    'What groups operate in telecom?',
    'Which companies share directors?',
  ]

  return (
    <div className="search-panel">
      <section className="search-section">
        <h2>Search Entities</h2>
        <form onSubmit={handleSearch}>
          <input
            type="text"
            placeholder="Search companies, people..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="search-input"
          />
          <button type="submit" className="search-button" disabled={loading}>
            {loading ? 'Searching...' : 'Search'}
          </button>
        </form>

        {searchResults.length > 0 && (
          <div className="results">
            <h3>Results ({searchResults.length})</h3>
            <ul className="results-list">
              {searchResults.map((result, i) => (
                <li
                  key={i}
                  onClick={() => onSelectEntity(result.name)}
                  className="result-item"
                >
                  <strong>{result.name}</strong>
                  <span className="entity-type">{result.type}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section className="query-section">
        <h2>Ask a Question</h2>
        <form onSubmit={handleNaturalLanguageQuery}>
          <textarea
            placeholder="Ask a natural language question..."
            value={naturalLanguageQuery}
            onChange={(e) => setNaturalLanguageQuery(e.target.value)}
            className="query-input"
            rows="3"
          />
          <button type="submit" className="search-button" disabled={loading}>
            {loading ? 'Processing...' : 'Ask'}
          </button>
        </form>

        <div className="examples">
          <p>Example questions:</p>
          <ul>
            {exampleQuestions.map((q, i) => (
              <li key={i} onClick={() => setNaturalLanguageQuery(q)}>
                {q}
              </li>
            ))}
          </ul>
        </div>

        {nlResults && !nlResults.error && (
          <div className="nl-results">
            <h3>Results</h3>
            <p className="interpretation">{nlResults.interpretation}</p>
            {nlResults.results && nlResults.results.length > 0 ? (
              <div className="results-table">
                {nlResults.results.map((row, i) => (
                  <div key={i} className="result-row">
                    {Object.entries(row).map(([key, value]) => (
                      <div key={key}>
                        <strong>{key}:</strong> {value}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            ) : (
              <p>No results found.</p>
            )}
          </div>
        )}

        {nlResults && nlResults.error && (
          <div className="error">{nlResults.error}</div>
        )}
      </section>
    </div>
  )
}

export default SearchPanel

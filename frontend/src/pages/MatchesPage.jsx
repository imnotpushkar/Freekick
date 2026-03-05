// src/pages/MatchesPage.jsx
//
// The main page — renders a grid of all finished matches.
// Fetches GET /api/matches on component mount.
//
// REACT HOOKS USED:
//
// useState — stores the matches array and loading/error states.
//   Three state variables because there are three distinct UI states:
//   loading (show spinner), error (show message), data (show cards).
//
// useEffect — runs side effects after render.
//   A "side effect" is anything outside the render itself:
//   API calls, timers, DOM manipulation.
//   useEffect(fn, []) — the empty array [] is the DEPENDENCY ARRAY.
//   An empty dependency array means "run this effect ONCE after
//   the first render and never again." This is how you fetch data
//   on page load. If you omitted the [], it would run after EVERY
//   render — causing an infinite loop (fetch → setState → render → fetch...).

import { useState, useEffect } from 'react'
import MatchCard from '../components/MatchCard'
import apiClient from '../api/client'

function MatchesPage() {
  const [matches, setMatches] = useState([])       // array of match objects
  const [loading, setLoading] = useState(true)     // true while fetching
  const [error, setError] = useState(null)         // error message string or null

  useEffect(() => {
    // Define async function inside useEffect.
    // useEffect itself cannot be async directly — it must return
    // either nothing or a cleanup function, not a Promise.
    // So the pattern is: define async fn, then call it immediately.
    const fetchMatches = async () => {
      try {
        // apiClient.get returns a Promise that resolves to an Axios response.
        // response.data is the parsed JSON body — the array of match objects.
        const response = await apiClient.get('/api/matches?limit=50')
        setMatches(response.data)
      } catch (err) {
        console.error('Failed to fetch matches:', err)
        setError('Could not load matches. Is the Flask API running?')
      } finally {
        setLoading(false)
      }
    }

    fetchMatches()
  }, []) // Empty dependency array — run once on mount

  // --- RENDER STATES ---

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto px-6 py-12">
        <div className="flex items-center justify-center gap-3 text-chalk-400">
          <span className="inline-block w-5 h-5 border-2 border-chalk-400 border-t-transparent rounded-full animate-spin" />
          <span>Loading matches...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-6xl mx-auto px-6 py-12">
        <div className="bg-red-950/50 border border-red-800 rounded-lg p-6">
          <p className="text-red-400">{error}</p>
          <p className="text-chalk-400 text-sm mt-2">
            Make sure Flask is running: <code className="text-grass-400">python -m backend.api.app</code>
          </p>
        </div>
      </div>
    )
  }

  // Group matches by competition for better readability
  const byCompetition = matches.reduce((acc, match) => {
    const comp = match.competition || 'Other'
    if (!acc[comp]) acc[comp] = []
    acc[comp].push(match)
    return acc
  }, {})

  // reduce() explained:
  // It iterates over the matches array, building up 'acc' (accumulator).
  // For each match, it adds the match to the right competition group.
  // Result: { "Premier League": [...], "La Liga": [...], ... }

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">

      {/* Page header */}
      <div className="mb-8">
        <h1 className="font-display text-4xl text-chalk-100 tracking-wider">
          MATCH ANALYSIS
        </h1>
        <p className="text-chalk-400 text-sm mt-1">
          {matches.length} matches · click any match to read the full analysis
        </p>
      </div>

      {matches.length === 0 ? (
        <div className="bg-card border border-pitch-800 rounded-lg p-8 text-center">
          <p className="text-chalk-400">No matches found. Run the pipeline to fetch data.</p>
        </div>
      ) : (
        // Render matches grouped by competition
        Object.entries(byCompetition).map(([competition, compMatches]) => (
          <div key={competition} className="mb-10">

            {/* Competition header */}
            <div className="flex items-center gap-3 mb-4">
              <h2 className="font-display text-xl text-grass-400 tracking-wider uppercase">
                {competition}
              </h2>
              <div className="flex-1 h-px bg-pitch-800" />
              <span className="text-xs text-chalk-400">{compMatches.length} matches</span>
            </div>

            {/* Match cards grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {compMatches.map(match => (
                // key prop — React requires a unique key for list items.
                // React uses keys to identify which items changed, were added,
                // or were removed. Without keys, React re-renders the entire list.
                <MatchCard key={match.id} match={match} />
              ))}
            </div>

          </div>
        ))
      )}
    </div>
  )
}

export default MatchesPage

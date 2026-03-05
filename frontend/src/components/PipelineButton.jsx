// src/components/PipelineButton.jsx
//
// Triggers POST /api/pipeline/run — the full 7-step backend pipeline.
//
// REACT HOOKS USED:
// useState — manages local component state.
//   React re-renders the component whenever state changes.
//   const [loading, setLoading] = useState(false)
//   'loading' is the current value, 'setLoading' is the setter function.
//   You NEVER mutate state directly (loading = true is wrong).
//   You always call the setter (setLoading(true) is correct).
//
// WHY LOADING STATE:
// The pipeline takes ~22 seconds. Without loading state, the user
// gets zero feedback and might click multiple times. We disable
// the button and show a spinner while the request is in flight.

import { useState } from 'react'
import apiClient from '../api/client'

function PipelineButton() {
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState(null) // null | 'success' | 'error'

  const runPipeline = async () => {
    // Prevent double-clicks while already running
    if (loading) return

    setLoading(true)
    setStatus(null)

    try {
      // POST request — no body needed, the endpoint takes no parameters
      await apiClient.post('/api/pipeline/run')
      setStatus('success')

      // Clear success message after 4 seconds
      setTimeout(() => setStatus(null), 4000)

    } catch (err) {
      console.error('Pipeline failed:', err)
      setStatus('error')
      setTimeout(() => setStatus(null), 4000)

    } finally {
      // finally always runs — whether try succeeded or catch triggered.
      // Same pattern as your Flask DB session cleanup in routes.py.
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center gap-3">

      {/* Status message — only renders when status is not null */}
      {status === 'success' && (
        <span className="text-grass-400 text-sm">Pipeline complete ✓</span>
      )}
      {status === 'error' && (
        <span className="text-red-400 text-sm">Pipeline failed ✗</span>
      )}

      <button
        onClick={runPipeline}
        disabled={loading}
        className={`
          px-4 py-2 rounded border text-sm font-body font-medium
          transition-all duration-200
          ${loading
            ? 'border-pitch-800 text-chalk-400 cursor-not-allowed'
            : 'border-grass-400 text-grass-400 hover:bg-grass-400 hover:text-pitch-950 cursor-pointer'
          }
        `}
      >
        {/* Conditional rendering based on loading state */}
        {loading ? (
          <span className="flex items-center gap-2">
            {/* CSS spinner — pure Tailwind, no library needed */}
            <span className="inline-block w-3 h-3 border-2 border-chalk-400 border-t-transparent rounded-full animate-spin" />
            Running...
          </span>
        ) : (
          'Run Pipeline'
        )}
      </button>
    </div>
  )
}

export default PipelineButton

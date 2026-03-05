// src/pages/MatchDetailPage.jsx
//
// Shows full analysis for a single match.
// URL: /matches/:id
//
// NEW HOOK: useParams()
// Reads URL parameters defined in the Route path.
// Route path="/matches/:id" → useParams() returns { id: "123" }
// This is how the component knows WHICH match to fetch.
//
// We make TWO parallel API calls using Promise.all():
//   GET /api/matches/:id/summary — AI analysis text
//   GET /api/matches/:id/events  — goals, cards, subs
//
// Promise.all([p1, p2]) waits for BOTH promises to resolve,
// then returns [result1, result2]. This is faster than two
// sequential awaits because both requests run simultaneously.

import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import apiClient from '../api/client'
import SummaryPanel from '../components/SummaryPanel'
import EventsTimeline from '../components/EventsTimeline'

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('en-GB', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  })
}

function MatchDetailPage() {
  // useParams reads :id from the URL
  const { id } = useParams()

  const [match, setMatch] = useState(null)
  const [summary, setSummary] = useState(null)
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetchMatchData = async () => {
      try {
        // Promise.all — runs all three requests simultaneously.
        // Much faster than three sequential awaits.
        // If ANY promise rejects, the whole Promise.all rejects immediately.
        const [matchRes, summaryRes, eventsRes] = await Promise.all([
          apiClient.get(`/api/matches/${id}`),
          apiClient.get(`/api/matches/${id}/summary`).catch(() => ({ data: { summary: null } })),
          apiClient.get(`/api/matches/${id}/events`).catch(() => ({ data: [] })),
        ])
        // Note: summary and events use .catch() individually so a missing
        // summary doesn't crash the entire page. Graceful degradation —
        // same principle as your backend scrapers.

        setMatch(matchRes.data)
        setSummary(summaryRes.data.summary || null)
        setEvents(eventsRes.data)

      } catch (err) {
        console.error('Failed to load match:', err)
        setError('Could not load match data.')
      } finally {
        setLoading(false)
      }
    }

    fetchMatchData()
  }, [id]) // id in dependency array — if URL changes, re-fetch

  // --- RENDER STATES ---

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-6 py-12">
        <div className="flex items-center gap-3 text-chalk-400">
          <span className="inline-block w-5 h-5 border-2 border-chalk-400 border-t-transparent rounded-full animate-spin" />
          <span>Loading match...</span>
        </div>
      </div>
    )
  }

  if (error || !match) {
    return (
      <div className="max-w-5xl mx-auto px-6 py-12">
        <div className="bg-red-950/50 border border-red-800 rounded-lg p-6">
          <p className="text-red-400">{error || 'Match not found.'}</p>
          <Link to="/" className="text-grass-400 text-sm mt-2 block hover:underline">
            ← Back to all matches
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">

      {/* Back link */}
      <Link
        to="/"
        className="text-chalk-400 text-sm hover:text-grass-400 transition-colors mb-6 block"
      >
        ← All matches
      </Link>

      {/* Match header card */}
      <div className="bg-card border border-pitch-800 rounded-lg p-8 mb-8">

        {/* Competition + date */}
        <div className="flex items-center justify-between mb-6">
          <span className="text-grass-400 text-sm font-medium uppercase tracking-wider">
            {match.competition}
            {match.matchday && <span className="text-chalk-400"> · MD {match.matchday}</span>}
          </span>
          <span className="text-chalk-400 text-sm">{formatDate(match.utc_date)}</span>
        </div>

        {/* Score display */}
        <div className="flex items-center justify-center gap-8">

          <div className="flex-1 text-right">
            <h2 className="text-chalk-100 text-xl font-medium">{match.home_team}</h2>
            <p className="text-chalk-400 text-xs mt-1">Home</p>
          </div>

          <div className="text-center shrink-0">
            <div className="flex items-center gap-2">
              <span className="font-display text-6xl text-chalk-100">
                {match.home_score ?? '-'}
              </span>
              <span className="font-display text-4xl text-pitch-800 mx-1">:</span>
              <span className="font-display text-6xl text-chalk-100">
                {match.away_score ?? '-'}
              </span>
            </div>
            <p className="text-chalk-400 text-xs mt-1 uppercase tracking-widest">
              Full Time
            </p>
          </div>

          <div className="flex-1 text-left">
            <h2 className="text-chalk-100 text-xl font-medium">{match.away_team}</h2>
            <p className="text-chalk-400 text-xs mt-1">Away</p>
          </div>

        </div>
      </div>

      {/* Two-column layout on larger screens — events left, summary right */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Events column — narrower */}
        <div className="lg:col-span-1">
          <EventsTimeline events={events} />
        </div>

        {/* Summary column — wider */}
        <div className="lg:col-span-2">
          <SummaryPanel summary={summary} />
        </div>

      </div>

    </div>
  )
}

export default MatchDetailPage

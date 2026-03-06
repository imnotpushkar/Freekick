// src/pages/MatchesPage.jsx
//
// Reusable match list page — used by all competition pages.
//
// PROPS:
//   competition: object with shape:
//     {
//       code:      "PL"               — passed to API as ?competition=PL
//       name:      "Premier League"   — shown in hero eyebrow
//       label:     "PREMIER LEAGUE"   — shown in hero heading
//       Badge:     <Component />      — SVG badge component from Navbar
//     }
//
// WHY PROPS INSTEAD OF SEPARATE PAGE FILES:
//   All competition pages share identical layout and behaviour.
//   The only differences are the API filter code and the hero text.
//   Passing these as props means one component handles everything —
//   no code duplication. Each competition page file is just 10 lines.
//
// API CALL:
//   /api/matches?competition=PL&limit=20
//   The backend joins to the Competition table and filters by code.
//   No competition code = all competitions returned (not used here).
//
// MATCH GROUPING:
//   Previously MatchesPage grouped matches by competition using
//   byCompetition reduce(). That was needed when one page showed
//   all competitions. Now each page is one competition — the grouping
//   is replaced with a simpler matchday grouping instead.

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import MatchCard from '../components/MatchCard'
import MatchTransition from '../components/MatchTransition'
import GiveAndGo from '../components/animations/GiveAndGo'
import apiClient from '../api/client'

// Default competition config — Premier League
// Used when MatchesPage is rendered without props (direct route to /)
const DEFAULT_COMPETITION = {
  code:  'PL',
  name:  'Premier League',
  label: 'PREMIER LEAGUE',
}

export default function MatchesPage({ competition = DEFAULT_COMPETITION }) {
  const [matches, setMatches]                 = useState([])
  const [loading, setLoading]                 = useState(true)
  const [error, setError]                     = useState(null)
  const [transitionState, setTransitionState] = useState(null)
  const navigate = useNavigate()

  // Re-fetch when competition changes (user switches tab in navbar)
  // The competition.code in the dependency array ensures a new fetch
  // fires whenever the user navigates to a different competition page.
  useEffect(() => {
    setLoading(true)
    setError(null)
    setMatches([])

    apiClient.get('/api/matches', {
      params: {
        competition: competition.code,
        limit: 20,
      }
    })
      .then(res => setMatches(res.data))
      .catch(() => setError('Could not load matches. Is the Flask API running?'))
      .finally(() => setLoading(false))
  }, [competition.code])

  const handleMatchClick = (match, animationType) => {
    setTransitionState({ match, animationType })
  }

  const handleTransitionDone = () => {
    const id = transitionState?.match?.id
    setTransitionState(null)
    if (id) navigate(`/matches/${id}`)
  }

  // Group matches by matchday for display
  // reduce() builds an object: { 29: [...matches], 28: [...matches] }
  // Object.entries() then converts it to pairs we can map over
  const byMatchday = matches.reduce((acc, match) => {
    const md = match.matchday || 'Unknown'
    if (!acc[md]) acc[md] = []
    acc[md].push(match)
    return acc
  }, {})

  // Sort matchdays descending (most recent first)
  const sortedMatchdays = Object.keys(byMatchday)
    .map(Number)
    .sort((a, b) => b - a)

  // ── Loading state ────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="max-w-6xl mx-auto px-6 py-12 flex items-center gap-3 text-textmuted">
        <span className="w-4 h-4 border-2 border-textmuted border-t-transparent rounded-full animate-spin inline-block"/>
        <span className="font-condensed tracking-widest uppercase text-xs">
          Loading {competition.name} matches...
        </span>
      </div>
    )
  }

  // ── Error state ──────────────────────────────────────────────────────────
  if (error) {
    return (
      <div className="max-w-6xl mx-auto px-6 py-12">
        <div className="border border-fkred/30 bg-fkred/5 p-6">
          <p className="text-fkred font-condensed">{error}</p>
          <p className="text-textmuted text-sm mt-2 font-condensed">
            Run: <code className="text-fkgreenbright">python -m backend.api.app</code>
          </p>
        </div>
      </div>
    )
  }

  return (
    <>
      {/* ── Transition overlay — mounts on card click ─────────────────────── */}
      {transitionState && (
        <MatchTransition
          animationType={transitionState.animationType}
          matchData={transitionState.match}
          onDone={handleTransitionDone}
        />
      )}

      {/* ── HERO SECTION ──────────────────────────────────────────────────── */}
      {/*
        Height: calc(100dvh - 88px) accounts for navbar (56px) + ticker (32px).
        dvh = dynamic viewport height — handles mobile browser chrome correctly.
      */}
      <div
        style={{ height: 'calc(100dvh - 88px)', minHeight: 480 }}
        className="relative flex flex-col items-center justify-center overflow-hidden bg-bg"
      >
        {/* Dot grid background */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage: 'radial-gradient(circle, rgba(69,196,102,0.07) 1px, transparent 1px)',
            backgroundSize: '28px 28px',
          }}
        />

        {/* Vignette */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: 'radial-gradient(ellipse at center, transparent 30%, #100e0b 80%)',
          }}
        />

        {/* Ground line */}
        <div
          className="absolute pointer-events-none"
          style={{
            bottom: 88,
            left: '15%',
            right: '15%',
            height: 1,
            background: 'linear-gradient(90deg, transparent 0%, rgba(69,196,102,0.25) 30%, rgba(69,196,102,0.5) 50%, rgba(69,196,102,0.25) 70%, transparent 100%)',
          }}
        />
        {/* Ground glow */}
        <div
          className="absolute pointer-events-none"
          style={{
            bottom: 80,
            left: '50%',
            transform: 'translateX(-50%)',
            width: 200,
            height: 18,
            background: 'radial-gradient(ellipse, rgba(69,196,102,0.12), transparent)',
          }}
        />

        {/* Hero content */}
        <div className="relative z-10 flex flex-col items-center text-center">

          {/* Eyebrow — competition name */}
          <p className="font-condensed text-xs font-bold tracking-widest uppercase text-fkgreenbright mb-3">
            {competition.name} · Match Intelligence
          </p>

          {/* Wordmark */}
          <h1
            className="font-display text-textprimary leading-none mb-3"
            style={{ fontSize: 'clamp(72px, 12vw, 120px)', letterSpacing: 6 }}
          >
            FREE<span
              className="text-fkgreenbright"
              style={{ textShadow: '0 0 60px rgba(69,196,102,0.35)' }}
            >KICK</span>
          </h1>

          {/* Subtitle */}
          <p className="font-condensed text-xs tracking-widest uppercase text-textsecondary mb-10">
            Creator-quality tactical analysis
          </p>

          {/* GiveAndGo animation */}
          <GiveAndGo />

        </div>

        {/* Scroll hint */}
        <p
          className="absolute bottom-6 font-condensed text-xs tracking-widest uppercase text-textmuted"
          style={{ animation: 'fk-blink 2.2s ease-in-out infinite' }}
        >
          ↓ Scroll to view matches
        </p>
      </div>

      {/* ── MATCH LIST ────────────────────────────────────────────────────── */}
      <div className="max-w-6xl mx-auto px-6 py-8">

        {/* Section header */}
        <div className="mb-8 flex items-end justify-between">
          <div>
            <h2 className="font-display text-4xl text-textprimary tracking-wider">
              MATCH ANALYSIS
            </h2>
            <p className="font-condensed text-xs text-textmuted tracking-widest uppercase mt-1">
              {competition.name} · {matches.length} matches · click any match to read
            </p>
          </div>
        </div>

        {matches.length === 0 ? (
          <div className="bg-surface border border-bdr p-8 text-center">
            <p className="text-textmuted font-condensed">
              No {competition.name} matches found. Run the pipeline to fetch data.
            </p>
            <p className="text-textmuted text-xs font-condensed mt-2 opacity-60">
              python -m backend.main --competition {competition.code}
            </p>
          </div>
        ) : (
          sortedMatchdays.map(md => (
            <div key={md} className="mb-10">
              {/* Matchday header */}
              <div className="bg-surface3 border-l-4 border-fkgreen border-b border-bdr px-6 py-2.5 flex items-center gap-4">
                <span className="font-condensed text-xs font-bold tracking-widest uppercase text-textprimary">
                  Matchday {md}
                </span>
                <div className="flex-1 h-px bg-bdr"/>
                <span className="font-condensed text-xs text-fkgreenbright tracking-wider">
                  {byMatchday[md].length} matches
                </span>
              </div>
              {/* Card grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 border-l border-t border-bdr">
                {byMatchday[md].map(match => (
                  <div key={match.id} className="border-r border-b border-bdr">
                    <MatchCard match={match} onMatchClick={handleMatchClick}/>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </>
  )
}

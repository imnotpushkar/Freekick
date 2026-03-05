// src/components/MatchCard.jsx
//
// Displays one match in the matches list.
// Receives match data as a PROP — props are how parent components
// pass data down to child components in React.
//
// PROPS:
// Think of props like function arguments for components.
// <MatchCard match={matchObject} /> passes matchObject as the 'match' prop.
// Inside the component, we destructure: function MatchCard({ match })
// This is identical to: function MatchCard(props) { const match = props.match }
//
// Link from react-router-dom — clicking the card navigates to
// /matches/:id without a full page reload.

import { Link } from 'react-router-dom'

// Helper to format ISO date strings to readable format
// e.g. "2024-12-15T15:00:00Z" → "15 Dec 2024"
function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

function MatchCard({ match }) {
  // Safely extract data — API may return null for some fields
  const homeTeam = match.home_team || 'Home'
  const awayTeam = match.away_team || 'Away'
  const homeScore = match.home_score ?? '-'
  const awayScore = match.away_score ?? '-'
  const competition = match.competition || ''
  const matchday = match.matchday ? `MD ${match.matchday}` : ''
  const date = formatDate(match.utc_date)
  const hasSummary = match.has_summary  // boolean flag from API

  return (
    // The entire card is a Link — clicking anywhere navigates to match detail
    <Link
      to={`/matches/${match.id}`}
      className="block group"
    >
      <div className="
        bg-card border border-pitch-800 rounded-lg p-5
        hover:bg-card-hover hover:border-grass-400/30
        transition-all duration-200
        relative overflow-hidden
      ">

        {/* Top row — competition + date */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <span className="text-xs text-grass-400 font-medium uppercase tracking-wider">
              {competition}
            </span>
            {matchday && (
              <span className="text-xs text-chalk-400">· {matchday}</span>
            )}
          </div>
          <span className="text-xs text-chalk-400">{date}</span>
        </div>

        {/* Score row — the main visual element */}
        <div className="flex items-center justify-between gap-4">

          {/* Home team */}
          <div className="flex-1 text-right">
            <span className="text-chalk-100 font-medium text-sm leading-tight">
              {homeTeam}
            </span>
          </div>

          {/* Score — Bebas Neue display font, large and prominent */}
          <div className="flex items-center gap-1 shrink-0">
            <span className="font-display text-3xl text-chalk-100 w-8 text-center">
              {homeScore}
            </span>
            <span className="text-chalk-400 text-lg mx-1">–</span>
            <span className="font-display text-3xl text-chalk-100 w-8 text-center">
              {awayScore}
            </span>
          </div>

          {/* Away team */}
          <div className="flex-1 text-left">
            <span className="text-chalk-100 font-medium text-sm leading-tight">
              {awayTeam}
            </span>
          </div>

        </div>

        {/* Bottom row — analysis badge */}
        <div className="mt-4 flex justify-end">
          {hasSummary ? (
            <span className="text-xs bg-grass-400/10 text-grass-400 border border-grass-400/20 px-2 py-0.5 rounded">
              Analysis ready
            </span>
          ) : (
            <span className="text-xs text-chalk-400">
              No analysis yet
            </span>
          )}
        </div>

        {/* Subtle left accent bar — appears on hover */}
        <div className="
          absolute left-0 top-0 bottom-0 w-0.5
          bg-grass-400 scale-y-0 group-hover:scale-y-100
          transition-transform duration-200 origin-center
        " />

      </div>
    </Link>
  )
}

export default MatchCard

/**
 * StatBar.jsx
 *
 * Animated side-by-side comparison bars for two teams.
 * Fetches GET /api/matches/<id>/stats which queries the match_stats table.
 *
 * WHAT match_stats STORES:
 *   Team-level aggregates from SofaScore's /match/statistics endpoint.
 *   Two rows per match — one for home team (is_home=true), one for away.
 *   This is different from player_stats which stores per-player data
 *   and is currently empty (reserved for future player-level sources).
 *
 * HOW THE ANIMATION WORKS:
 *   1. Component mounts → all bars render at width: '0%'
 *   2. useEffect fires → after 10ms, animationReady flips to true
 *   3. React re-renders → bars receive their real widths
 *   4. CSS `transition: width 800ms ease-out` interpolates the change
 *
 *   The 10ms delay is intentional. Without it, React batches the mount
 *   render and the state update into one paint — the browser never sees
 *   width:0% so the transition never fires. The delay forces two paints.
 *
 *   This is a CSS transition, not requestAnimationFrame. Use CSS for
 *   one-shot property animations. Use rAF for continuous 60fps loops.
 *
 * BAR WIDTH CALCULATION:
 *   Each bar = (team_value / combined_total) * 100%
 *   The two bars always sum to 100% of the container width.
 *   If both values are null or 0, we show 50/50 — no bars disappear.
 */

import { useState, useEffect } from 'react'
import { getMatchStats } from '../api/client'

/**
 * STAT_CONFIG
 * Defines which stats to display, in order.
 * key:      matches the field name returned by /api/matches/<id>/stats
 * label:    displayed above the bar
 * decimals: decimal places for the value display
 * unit:     optional suffix appended to the value (e.g. "%" for possession)
 *
 * Adding a new stat bar = one new object in this array. Nothing else changes.
 */
const STAT_CONFIG = [
  { key: 'possession',          label: 'Possession',         decimals: 1, unit: '%' },
  { key: 'xg',                  label: 'xG',                 decimals: 2, unit: ''  },
  { key: 'big_chances',         label: 'Big Chances',        decimals: 0, unit: ''  },
  { key: 'total_shots',         label: 'Shots',              decimals: 0, unit: ''  },
  { key: 'shots_on_target',     label: 'Shots on Target',    decimals: 0, unit: ''  },
  { key: 'shots_inside_box',    label: 'Shots Inside Box',   decimals: 0, unit: ''  },
  { key: 'passes',              label: 'Passes',             decimals: 0, unit: ''  },
  { key: 'pass_accuracy',       label: 'Pass Accuracy',      decimals: 1, unit: '%' },
  { key: 'tackles',             label: 'Tackles',            decimals: 0, unit: ''  },
  { key: 'interceptions',       label: 'Interceptions',      decimals: 0, unit: ''  },
  { key: 'recoveries',          label: 'Ball Recoveries',    decimals: 0, unit: ''  },
  { key: 'fouls',               label: 'Fouls',              decimals: 0, unit: ''  },
  { key: 'goalkeeper_saves',    label: 'GK Saves',           decimals: 0, unit: ''  },
]

/**
 * formatVal — formats a number for display.
 * Returns '—' for null/undefined (no fake zeros).
 * Appends unit string if provided.
 */
function formatVal(value, decimals, unit = '') {
  if (value === null || value === undefined) return '—'
  return `${Number(value).toFixed(decimals)}${unit}`
}

/**
 * StatRow — renders one stat comparison line.
 *
 * The visual structure is:
 *   [home value]  [====home bar===][===away bar====]  [away value]
 *
 * Both bars live in a single flex container. Home grows left-to-right,
 * away grows left-to-right after it — together they fill the container.
 * The visual impression is home pressing from the left, away from the right.
 */
function StatRow({ label, homeVal, awayVal, decimals, unit, animationReady }) {
  const home = homeVal ?? 0
  const away = awayVal ?? 0
  const total = home + away

  // If neither team has data, render 50/50 so the bar still shows
  const homePct = total === 0 ? 50 : (home / total) * 100
  const awayPct = total === 0 ? 50 : (away / total) * 100

  // If both values are null (not zero), dim the row to signal missing data
  const isMissing = homeVal === null && awayVal === null

  return (
    <div className={`mb-5 ${isMissing ? 'opacity-40' : ''}`}>
      {/* Stat label */}
      <p className="font-condensed text-xs font-bold tracking-widest uppercase text-fk-textmuted text-center mb-1.5">
        {label}
      </p>

      <div className="flex items-center gap-3">
        {/* Home value */}
        <span className="font-display text-xl text-fk-textprimary w-14 text-right leading-none shrink-0">
          {formatVal(homeVal, decimals, unit)}
        </span>

        {/* Bar track */}
        <div className="flex-1 flex h-2 rounded-full overflow-hidden bg-fk-bg gap-px">
          {/* Home bar — fk-greenlight, grows from left */}
          <div
            style={{
              width: animationReady ? `${homePct}%` : '0%',
              transition: 'width 800ms ease-out',
              backgroundColor: '#2da050',
              borderRadius: '9999px 0 0 9999px',
            }}
          />
          {/* Away bar — fk-amber, fills remainder */}
          <div
            style={{
              width: animationReady ? `${awayPct}%` : '0%',
              transition: 'width 800ms ease-out 40ms',
              backgroundColor: '#c8780a',
              borderRadius: '0 9999px 9999px 0',
            }}
          />
        </div>

        {/* Away value */}
        <span className="font-display text-xl text-fk-textprimary w-14 text-left leading-none shrink-0">
          {formatVal(awayVal, decimals, unit)}
        </span>
      </div>
    </div>
  )
}

/**
 * StatBar — main exported component.
 * Owns its own data fetching. MatchDetailPage only passes matchId.
 */
function StatBar({ matchId }) {
  const [stats, setStats]                   = useState(null)
  const [loading, setLoading]               = useState(true)
  const [error, setError]                   = useState(null)
  const [animationReady, setAnimationReady] = useState(false)

  useEffect(() => {
    if (!matchId) return
    setLoading(true)
    getMatchStats(matchId)
      .then(data => {
        setStats(data)
        setLoading(false)
        // Schedule animation trigger after current paint cycle
        setTimeout(() => setAnimationReady(true), 10)
      })
      .catch(err => {
        setError(err.message)
        setLoading(false)
      })
  }, [matchId])

  if (loading) {
    return (
      <div className="bg-fk-surface border border-fk-bdr rounded-sm p-6">
        <p className="font-condensed text-xs tracking-widest uppercase text-fk-textmuted animate-pulse">
          Loading stats...
        </p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-fk-surface border border-fk-bdr rounded-sm p-6">
        <p className="font-condensed text-xs tracking-widest uppercase text-fk-red">
          Stats unavailable
        </p>
      </div>
    )
  }

  if (!stats || !stats.available) {
    return (
      <div className="bg-fk-surface border border-fk-bdr rounded-sm p-6">
        <p className="font-condensed text-xs tracking-widest uppercase text-fk-textmuted">
          No stats recorded — pipeline not run for this match.
        </p>
      </div>
    )
  }

  return (
    <div className="bg-fk-surface border border-fk-bdr rounded-sm overflow-hidden">
      {/* Section header */}
      <div className="bg-fk-green px-6 py-3">
        <h3 className="font-condensed text-xs font-bold tracking-widest uppercase text-white/85">
          Match Stats
        </h3>
      </div>

      {/* Team name headers — green for home, amber for away */}
      <div className="flex justify-between px-6 pt-4 pb-3 border-b border-fk-bdr">
        <span className="font-condensed text-sm font-semibold text-fk-greenbright">
          {stats.home?.team || 'Home'}
        </span>
        <span className="font-condensed text-sm font-semibold text-fk-amberbright">
          {stats.away?.team || 'Away'}
        </span>
      </div>

      <div className="px-6 pt-4 pb-2">
        {STAT_CONFIG.map(({ key, label, decimals, unit }) => (
          <StatRow
            key={key}
            label={label}
            homeVal={stats.home?.[key] ?? null}
            awayVal={stats.away?.[key] ?? null}
            decimals={decimals}
            unit={unit}
            animationReady={animationReady}
          />
        ))}
      </div>
    </div>
  )
}

export default StatBar

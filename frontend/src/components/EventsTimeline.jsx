/**
 * EventsTimeline.jsx
 *
 * Renders the chronological list of match events: goals, cards, substitutions.
 *
 * PROPS:
 *   events — array from GET /api/matches/<id>/events
 *   Each event shape:
 *     { type, minute, player, secondary_player, detail, reason }
 *
 * EVENT TYPES AND WHAT secondary_player MEANS:
 *   goal         → secondary_player is the assist provider (may be null)
 *   card         → secondary_player is always null; reason may exist
 *   substitution → player = coming ON, secondary_player = coming OFF
 *                  (this is how the DB stores it — confirmed from API output)
 *
 * TAILWIND TOKEN PATTERN IN THIS PROJECT:
 *   All custom design tokens are prefixed with fk-
 *   e.g. bg-fk-surface, text-fk-textprimary, border-fk-bdr
 *   Missing this prefix means the class silently does nothing.
 */

/**
 * EventIcon
 * Returns the correct emoji/symbol for each event type and detail.
 * Kept as a pure presentational sub-component — no state, no side effects.
 */
function EventIcon({ eventType, detailType }) {
  if (eventType === 'goal') {
    if (detailType === 'penalty')  return <span title="Penalty Goal">⚽ P</span>
    if (detailType === 'own_goal') return <span title="Own Goal">⚽ OG</span>
    return <span title="Goal">⚽</span>
  }
  if (eventType === 'card') {
    if (detailType === 'yellow')    return <span title="Yellow Card">🟨</span>
    if (detailType === 'yellowRed') return <span title="Second Yellow / Red">🟨🟥</span>
    if (detailType === 'red')       return <span title="Red Card">🟥</span>
    return <span>🃏</span>
  }
  if (eventType === 'substitution') return <span title="Substitution">🔄</span>
  return <span>·</span>
}

/**
 * eventLabel
 * Returns a short uppercase label string for the event type row header.
 */
function eventLabel(eventType, detailType) {
  if (eventType === 'goal') {
    if (detailType === 'penalty')  return 'Penalty'
    if (detailType === 'own_goal') return 'Own Goal'
    return 'Goal'
  }
  if (eventType === 'card') {
    if (detailType === 'yellow')    return 'Yellow Card'
    if (detailType === 'yellowRed') return '2nd Yellow / Red'
    if (detailType === 'red')       return 'Red Card'
    return 'Card'
  }
  if (eventType === 'substitution') return 'Substitution'
  return eventType
}

/**
 * minuteColor / labelColor
 * Returns the correct Tailwind text colour class for the event type.
 * Goals → green, red/2nd yellow → red, yellow card → amber, rest → muted.
 */
function minuteColor(eventType, detailType) {
  if (eventType === 'goal') return 'text-fk-greenbright'
  if (eventType === 'card') {
    if (detailType === 'red' || detailType === 'yellowRed') return 'text-fk-red'
    return 'text-fk-amberbright'
  }
  return 'text-fk-textmuted'
}

function labelColor(eventType, detailType) {
  if (eventType === 'goal') return 'text-fk-greenbright'
  if (eventType === 'card') {
    if (detailType === 'red' || detailType === 'yellowRed') return 'text-fk-red'
    return 'text-fk-amberbright'
  }
  return 'text-fk-textmuted'
}

/**
 * EventsTimeline
 * Main exported component. Receives the events array and renders the list.
 */
function EventsTimeline({ events }) {

  // Empty state — shown when no events are recorded for the match
  if (!events || events.length === 0) {
    return (
      <div className="bg-fk-surface border border-fk-bdr rounded-sm">
        <div className="bg-fk-green px-6 py-3">
          <h3 className="font-condensed text-xs font-bold tracking-widest uppercase text-white/85">
            Match Events
          </h3>
        </div>
        <p className="text-fk-textmuted text-sm p-6 font-condensed tracking-wide">
          No events recorded.
        </p>
      </div>
    )
  }

  // Sort events ascending by minute — some DBs may not guarantee insert order
  const sorted = [...events].sort((a, b) => (a.minute || 0) - (b.minute || 0))

  return (
    <div className="bg-fk-surface border border-fk-bdr rounded-sm overflow-hidden">

      {/* Section header — dark green bar matching the V3C design system */}
      <div className="bg-fk-green px-6 py-3">
        <h3 className="font-condensed text-xs font-bold tracking-widest uppercase text-white/85">
          Match Events
        </h3>
      </div>

      <div>
        {sorted.map((event, index) => (
          <div
            key={index}
            className="grid border-b border-fk-bdr last:border-b-0 hover:bg-fk-surface2 transition-colors duration-100"
            style={{
              gridTemplateColumns: '44px 24px 1fr',
              gap: '10px',
              padding: '12px 20px',
              alignItems: 'start',
            }}
          >
            {/* Minute badge — large Bebas Neue number, colour coded by event type */}
            <span className={`font-display text-xl text-right leading-tight ${minuteColor(event.type, event.detail)}`}>
              {event.minute}'
            </span>

            {/* Icon — emoji representing the event */}
            <span className="text-sm pt-0.5">
              <EventIcon eventType={event.type} detailType={event.detail} />
            </span>

            {/* Detail block — label + player name + secondary info */}
            <div>
              {/* Event type label e.g. GOAL / YELLOW CARD / SUBSTITUTION */}
              <p className={`font-condensed text-xs font-bold tracking-widest uppercase leading-none ${labelColor(event.type, event.detail)}`}>
                {eventLabel(event.type, event.detail)}
              </p>

              {/* Primary player name */}
              <p className="font-condensed text-sm font-semibold text-fk-textprimary leading-tight mt-0.5">
                {event.player || 'Unknown'}
              </p>

              {/*
                GOAL: show assist if secondary_player is present.
                No assist on penalties (secondary_player is null for those anyway).
              */}
              {event.type === 'goal' && event.secondary_player && (
                <p className="text-xs text-fk-textmuted italic mt-0.5">
                  Assist: {event.secondary_player}
                </p>
              )}

              {/*
                SUBSTITUTION: player = coming ON, secondary_player = coming OFF.
                ↑ / ↓ arrows are cleaner than text labels in a compact row.
                The arrow direction matches the physical movement:
                  ↑ = entering the pitch (player in the primary field)
                  ↓ = leaving the pitch (secondary_player)
              */}
              {event.type === 'substitution' && event.secondary_player && (
                <p className="text-xs text-fk-textmuted mt-0.5">
                  <span className="text-fk-greenbright font-bold">↑</span> {event.player}
                  <span className="mx-1 text-fk-textmuted">·</span>
                  <span className="text-fk-red font-bold">↓</span> {event.secondary_player}
                </p>
              )}

              {/*
                CARD: show the reason for the card if recorded.
                e.g. "Time wasting", "Foul", "Argument"
              */}
              {event.type === 'card' && event.reason && (
                <p className="text-xs text-fk-textmuted italic mt-0.5">
                  {event.reason}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default EventsTimeline

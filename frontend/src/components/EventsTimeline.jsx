// src/components/EventsTimeline.jsx
//
// FIX IN THIS VERSION:
// 'type' is a reserved HTML attribute (used on <input type="text"> etc).
// When we passed type="card" as a prop to EventIcon, React was treating
// it as an HTML attribute on the underlying element rather than a React
// prop — causing the component to receive undefined instead of "card".
// Renamed to eventType and detail to detailType to avoid the conflict.
//
// LESSON: Avoid using HTML reserved attribute names as React prop names.
// Common reserved names to avoid: type, class (use className), for (use
// htmlFor), name, value, checked, selected, disabled, readonly.

function EventIcon({ eventType, detailType }) {
  if (eventType === 'goal') {
    if (detailType === 'penalty') return <span>⚽ P</span>
    if (detailType === 'own_goal') return <span>⚽ OG</span>
    return <span>⚽</span>
  }
  if (eventType === 'card') {
    if (detailType === 'yellow') return <span>🟨</span>
    if (detailType === 'yellowRed') return <span>🟨🟥</span>
    if (detailType === 'red') return <span>🟥</span>
    return <span>🃏</span>
  }
  if (eventType === 'substitution') return <span>🔄</span>
  return <span>•</span>
}

function eventLabel(eventType, detailType) {
  if (eventType === 'goal') {
    if (detailType === 'penalty') return 'Penalty'
    if (detailType === 'own_goal') return 'Own Goal'
    return 'Goal'
  }
  if (eventType === 'card') {
    if (detailType === 'yellow') return 'Yellow Card'
    if (detailType === 'yellowRed') return '2nd Yellow / Red'
    if (detailType === 'red') return 'Red Card'
    return 'Card'
  }
  if (eventType === 'substitution') {
    if (detailType === 'injury') return 'Sub (Injury)'
    return 'Substitution'
  }
  return eventType
}

function minuteColor(eventType, detailType) {
  if (eventType === 'goal') return 'text-grass-400'
  if (eventType === 'card') {
    if (detailType === 'red' || detailType === 'yellowRed') return 'text-red-400'
    return 'text-yellow-400'
  }
  return 'text-chalk-400'
}

function EventsTimeline({ events }) {
  if (!events || events.length === 0) {
    return (
      <div className="bg-card border border-pitch-800 rounded-lg p-6">
        <h3 className="font-display text-xl text-grass-400 tracking-wider mb-3">MATCH EVENTS</h3>
        <p className="text-chalk-400 text-sm">No events recorded for this match.</p>
      </div>
    )
  }

  const sorted = [...events].sort((a, b) => (a.minute || 0) - (b.minute || 0))

  return (
    <div className="bg-card border border-pitch-800 rounded-lg p-6">
      <h3 className="font-display text-xl text-grass-400 tracking-wider mb-5">
        MATCH EVENTS
      </h3>

      <div className="space-y-4">
        {sorted.map((event, index) => (
          <div key={index} className="flex items-start gap-3">

            {/* Minute */}
            <span className={`font-display text-lg w-10 shrink-0 text-right ${minuteColor(event.type, event.detail)}`}>
              {event.minute}'
            </span>

            {/* Icon — note: we pass eventType/detailType to avoid
                the HTML reserved attribute 'type' conflict */}
            <span className="text-base shrink-0 mt-0.5">
              <EventIcon eventType={event.type} detailType={event.detail} />
            </span>

            {/* Event details */}
            <div className="flex-1 min-w-0">

              <p className="text-chalk-400 text-xs uppercase tracking-wider mb-0.5">
                {eventLabel(event.type, event.detail)}
              </p>

              <p className="text-chalk-100 text-sm font-medium truncate">
                {event.player || 'Unknown'}
              </p>

              {event.type === 'goal' && event.secondary_player && (
                <p className="text-chalk-400 text-xs mt-0.5">
                  Assist: {event.secondary_player}
                </p>
              )}

              {event.type === 'substitution' && event.secondary_player && (
                <p className="text-chalk-400 text-xs mt-0.5">
                  On: {event.secondary_player}
                </p>
              )}

              {event.type === 'card' && event.reason && (
                <p className="text-chalk-400 text-xs mt-0.5">
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

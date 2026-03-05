// src/components/EventsTimeline.jsx
//
// Renders goals, cards, and substitutions in chronological order.
// Each event comes from GET /api/matches/:id/events
//
// EVENT OBJECT SHAPE (from your routes.py _event_to_dict()):
// {
//   id, match_id, event_type, minute, team, player, assist,
//   card_type, is_home
// }
// event_type: "goal" | "own_goal" | "penalty" | "yellow_card" |
//             "red_card" | "substitution"

function EventIcon({ eventType, cardType }) {
  // Returns the right emoji/symbol for each event type
  const icons = {
    goal: '⚽',
    own_goal: '⚽',     // we'll style this differently
    penalty: '⚽',
    yellow_card: '🟨',
    red_card: '🟥',
    substitution: '🔄',
  }
  return <span className="text-base">{icons[eventType] || '•'}</span>
}

function EventsTimeline({ events }) {
  if (!events || events.length === 0) {
    return (
      <div className="bg-card border border-pitch-800 rounded-lg p-6">
        <p className="text-chalk-400 text-sm">No events recorded for this match.</p>
      </div>
    )
  }

  // Sort events by minute ascending — API may not guarantee order
  const sorted = [...events].sort((a, b) => (a.minute || 0) - (b.minute || 0))

  return (
    <div className="bg-card border border-pitch-800 rounded-lg p-6">
      <h3 className="font-display text-xl text-grass-400 tracking-wider mb-5">
        MATCH EVENTS
      </h3>

      <div className="space-y-3">
        {sorted.map((event) => {
          // is_home determines which side of the timeline the event sits on.
          // Home events are left-aligned, away events right-aligned.
          // This mirrors how match events are displayed in football apps.
          const isHome = event.is_home

          return (
            <div
              key={event.id}
              className={`flex items-center gap-3 ${isHome ? 'flex-row' : 'flex-row-reverse'}`}
            >
              {/* Minute badge */}
              <span className="font-display text-lg text-grass-400 w-10 text-center shrink-0">
                {event.minute}'
              </span>

              {/* Event icon */}
              <EventIcon eventType={event.event_type} />

              {/* Event description */}
              <div className={`flex-1 ${isHome ? 'text-left' : 'text-right'}`}>
                <span className="text-chalk-100 text-sm font-medium">
                  {event.player || 'Unknown'}
                </span>

                {/* Assist — only for goals */}
                {event.assist && (
                  <span className="text-chalk-400 text-xs ml-1">
                    (assist: {event.assist})
                  </span>
                )}

                {/* Own goal label */}
                {event.event_type === 'own_goal' && (
                  <span className="text-red-400 text-xs ml-1">(OG)</span>
                )}

                {/* Penalty label */}
                {event.event_type === 'penalty' && (
                  <span className="text-chalk-400 text-xs ml-1">(pen)</span>
                )}

                {/* Team name in muted text below */}
                {event.team && (
                  <p className="text-chalk-400 text-xs mt-0.5">{event.team}</p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default EventsTimeline

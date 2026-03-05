// src/components/SummaryPanel.jsx
//
// FIX IN THIS VERSION:
// The AI summary starts with "\n\n## THE STORY..." — the leading
// whitespace before the first ## creates an empty phantom section
// when we split on "\n## ". We now filter out any section whose
// title is empty or under 3 characters, eliminating the lone "•".

function SummaryPanel({ summary }) {
  if (!summary) {
    return (
      <div className="bg-card border border-pitch-800 rounded-lg p-6">
        <p className="text-chalk-400 text-sm">No analysis available for this match.</p>
      </div>
    )
  }

  // Step 1: trim leading/trailing whitespace first
  const trimmed = summary.trim()

  // Step 2: split on ## to get raw section strings
  // We split on "## " (with space) to avoid splitting on mid-text ##
  const rawSections = trimmed
    .split(/\n?## /)
    .map(s => s.trim())
    .filter(Boolean)  // remove empty strings

  // Step 3: parse each section into { title, body }
  const sections = rawSections
    .map(section => {
      const newlineIndex = section.indexOf('\n')
      if (newlineIndex === -1) return { title: section.trim(), body: '' }
      return {
        title: section.slice(0, newlineIndex).trim(),
        body: section.slice(newlineIndex + 1).trim(),
      }
    })
    // Step 4: filter out phantom sections — title must be at least
    // 3 characters. This removes the empty leading section caused
    // by "\n\n## " at the start of the AI output.
    .filter(s => s.title.length >= 3)

  const icons = {
    'THE STORY OF THE MATCH': '📖',
    'TACTICAL BREAKDOWN': '🔢',
    'PLAYERS WHO MADE THE DIFFERENCE': '⭐',
    'THE VERDICT': '🏆',
  }

  function getIcon(title) {
    if (icons[title]) return icons[title]
    if (title.includes('STORY')) return '📖'
    if (title.includes('TACTICAL')) return '🔢'
    if (title.includes('PLAYER')) return '⭐'
    if (title.includes('VERDICT')) return '🏆'
    return null  // return null instead of '•' — no icon for unknown sections
  }

  return (
    <div className="space-y-4">
      {sections.map((section, index) => (
        <div key={index} className="bg-card border border-pitch-800 rounded-lg p-6">

          <div className="flex items-center gap-2 mb-3">
            {getIcon(section.title) && (
              <span className="text-lg">{getIcon(section.title)}</span>
            )}
            <h3 className="font-display text-xl text-grass-400 tracking-wider">
              {section.title}
            </h3>
          </div>

          <div className="text-chalk-100 text-sm leading-relaxed whitespace-pre-line">
            {section.body}
          </div>

        </div>
      ))}
    </div>
  )
}

export default SummaryPanel

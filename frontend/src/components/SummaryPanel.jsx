// src/components/SummaryPanel.jsx
//
// Renders the 4-section AI analysis text from Groq.
// The summary comes back as a single string with section headers.
// We parse it into sections here so each gets its own styled block.
//
// The AI output format (from summarize.py) is:
//   ## The Story\n...\n## Tactical Breakdown\n...\n## Players\n...\n## Verdict\n...
//
// We split on "## " to get individual sections, then render each.

function SummaryPanel({ summary }) {
  // Guard — if no summary text, show placeholder
  if (!summary) {
    return (
      <div className="bg-card border border-pitch-800 rounded-lg p-6">
        <p className="text-chalk-400 text-sm">No analysis available for this match.</p>
      </div>
    )
  }

  // Parse sections from the AI output string.
  // split(/\n## /) splits on newline + "## " pattern.
  // The first element may be empty or contain the first "## " header,
  // so we filter out empty strings.
  const rawSections = summary.split(/\n## /).filter(Boolean)

  // Each section looks like: "The Story\nContent here..."
  // We split on the first newline to separate title from body.
  const sections = rawSections.map(section => {
    // Remove leading "## " if the first section starts with it
    const cleaned = section.replace(/^## /, '')
    const newlineIndex = cleaned.indexOf('\n')
    if (newlineIndex === -1) return { title: cleaned, body: '' }
    return {
      title: cleaned.slice(0, newlineIndex).trim(),
      body: cleaned.slice(newlineIndex + 1).trim(),
    }
  })

  // Icon map for each section title
  const icons = {
    'The Story': '📖',
    'Tactical Breakdown': '🔢',
    'Players': '⭐',
    'Verdict': '🏆',
  }

  return (
    <div className="space-y-4">
      {sections.map((section, index) => (
        <div
          key={index}
          className="bg-card border border-pitch-800 rounded-lg p-6"
        >
          {/* Section header */}
          <div className="flex items-center gap-2 mb-3">
            <span className="text-lg">{icons[section.title] || '•'}</span>
            <h3 className="font-display text-xl text-grass-400 tracking-wider">
              {section.title.toUpperCase()}
            </h3>
          </div>

          {/* Section body — preserve line breaks from AI output.
              whitespace-pre-line renders \n as actual line breaks
              while still wrapping long lines normally. */}
          <p className="text-chalk-100 text-sm leading-relaxed whitespace-pre-line">
            {section.body}
          </p>
        </div>
      ))}
    </div>
  )
}

export default SummaryPanel

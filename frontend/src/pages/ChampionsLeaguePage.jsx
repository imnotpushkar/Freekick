// src/pages/ChampionsLeaguePage.jsx
//
// UEFA Champions League page.
// Thin wrapper — passes competition config to MatchesPage.
// All layout, fetching, and animation logic lives in MatchesPage.

import MatchesPage from './MatchesPage'

const CHAMPIONS_LEAGUE = {
  code:  'CL',
  name:  'UEFA Champions League',
  label: 'CHAMPIONS LEAGUE',
}

export default function ChampionsLeaguePage() {
  return <MatchesPage competition={CHAMPIONS_LEAGUE} />
}

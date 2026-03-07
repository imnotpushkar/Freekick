// src/pages/BundesligaPage.jsx
//
// Bundesliga page.
// Thin wrapper — passes competition config to MatchesPage.

import MatchesPage from './MatchesPage'

const BUNDESLIGA = {
  code:  'BL1',
  name:  'Bundesliga',
  label: 'BUNDESLIGA',
  path: '/bundesliga'
}

export default function BundesligaPage() {
  return <MatchesPage competition={BUNDESLIGA} />
}

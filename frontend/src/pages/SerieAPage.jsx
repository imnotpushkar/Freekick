// src/pages/SerieAPage.jsx
//
// Serie A page.
// Thin wrapper — passes competition config to MatchesPage.

import MatchesPage from './MatchesPage'

const SERIE_A = {
  code:  'SA',
  name:  'Serie A',
  label: 'SERIE A',
  path: '/serie-a'
}

export default function SerieAPage() {
  return <MatchesPage competition={SERIE_A} />
}

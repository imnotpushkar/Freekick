// src/pages/LaLigaPage.jsx
//
// La Liga page.
// Thin wrapper — passes competition config to MatchesPage.

import MatchesPage from './MatchesPage'

const LA_LIGA = {
  code:  'PD',
  name:  'La Liga',
  label: 'LA LIGA',
}

export default function LaLigaPage() {
  return <MatchesPage competition={LA_LIGA} />
}

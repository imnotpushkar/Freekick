// src/App.jsx
//
// ROOT component — wraps the entire React app.
//
// ROUTING STRUCTURE:
//   /                    → Premier League (MatchesPage with competition="PL")
//   /champions-league    → UEFA Champions League
//   /la-liga             → La Liga
//   /bundesliga          → Bundesliga
//   /serie-a             → Serie A
//   /matches/:id         → Match detail page (competition-agnostic)
//
// WHY SEPARATE ROUTE FILES INSTEAD OF ONE PAGE WITH PARAMS:
//   Each competition page is a separate route (/la-liga, /bundesliga etc.)
//   rather than a single /competition/:code route. This is intentional:
//   - Bookmarkable, shareable URLs that read naturally
//   - Navbar active state is trivial — useLocation() matches exact path
//   - Each page can have its own hero text, badge, and animation
//     without a giant switch statement
//   - Adding a new competition is one new route + one new page file

import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import Ticker from './components/Ticker'
import MatchesPage from './pages/MatchesPage'
import MatchDetailPage from './pages/MatchDetailPage'
import ChampionsLeaguePage from './pages/ChampionsLeaguePage'
import LaLigaPage from './pages/LaLigaPage'
import BundesligaPage from './pages/BundesligaPage'
import SerieAPage from './pages/SerieAPage'

function App() {
  return (
    <BrowserRouter>
      <Navbar />

      {/* Content pushed down by fixed navbar (64px = pt-16) */}
      <div className="pt-16 min-h-screen bg-bg flex flex-col">
        <Ticker />
        <main className="flex-1">
          <Routes>
            <Route path="/"                 element={<MatchesPage />} />
            <Route path="/champions-league" element={<ChampionsLeaguePage />} />
            <Route path="/la-liga"          element={<LaLigaPage />} />
            <Route path="/bundesliga"       element={<BundesligaPage />} />
            <Route path="/serie-a"          element={<SerieAPage />} />
            <Route path="/matches/:id"      element={<MatchDetailPage />} />
          </Routes>
        </main>
      </div>

    </BrowserRouter>
  )
}

export default App

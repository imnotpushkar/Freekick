// src/App.jsx
//
// This is the ROOT component of the entire React app.
// Every React app has one root component that wraps everything else.
//
// REACT ROUTER CONCEPTS:
// BrowserRouter — wraps the app, enables client-side routing.
//   "Client-side" means page changes happen in JavaScript without
//   a real browser navigation request. The URL changes but the
//   page does NOT reload — React just swaps which component renders.
//
// Routes — container that looks at the current URL and renders
//   the first Route whose path matches.
//
// Route — maps a URL path to a component.
//   path="/"            → renders MatchesPage
//   path="/matches/:id" → renders MatchDetailPage
//   :id is a URL parameter — a dynamic segment. If the URL is
//   /matches/123, then :id = "123". The component reads it
//   with the useParams() hook.
//
// Link / Navigate — React Router's way to change URLs without
//   a full page reload. We use these in child components.

import { BrowserRouter, Routes, Route } from 'react-router-dom'
import MatchesPage from './pages/MatchesPage'
import MatchDetailPage from './pages/MatchDetailPage'
import Navbar from './components/Navbar'

function App() {
  return (
    <BrowserRouter>
      {/* Navbar renders on every page — it's outside <Routes> */}
      <Navbar />

      {/* Main content area — shifts down to account for fixed navbar */}
      <main className="pt-16 min-h-screen bg-pitch-950">
        <Routes>
          <Route path="/" element={<MatchesPage />} />
          <Route path="/matches/:id" element={<MatchDetailPage />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}

export default App

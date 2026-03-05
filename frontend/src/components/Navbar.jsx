// src/components/Navbar.jsx
//
// Fixed top navigation bar present on all pages.
// 'fixed top-0' keeps it pinned to the top of the viewport.
// 'z-50' ensures it renders above all other content.
// This is why App.jsx adds 'pt-16' to main — to prevent content
// from hiding under the fixed navbar.

import { Link } from 'react-router-dom'
import PipelineButton from './PipelineButton'

function Navbar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-pitch-900 border-b border-pitch-800">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">

        {/* Logo — Link component changes URL without page reload */}
        <Link to="/" className="flex items-center gap-3 group">
          <span className="text-grass-400 text-2xl">⚽</span>
          <div>
            <span className="font-display text-2xl text-chalk-100 tracking-wider">
              FREEKICK
            </span>
            <span className="block text-xs text-chalk-400 -mt-1 tracking-widest uppercase">
              Match Intelligence
            </span>
          </div>
        </Link>

        {/* Right side — pipeline trigger */}
        <PipelineButton />

      </div>
    </nav>
  )
}

export default Navbar

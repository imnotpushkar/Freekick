// src/components/Navbar.jsx
//
// Fixed top navigation bar.
//
// COMPETITION BADGES:
//   Each competition has a custom SVG badge — geometric shapes in
//   that competition's colours. These are NOT copied logos (trademark
//   risk). They are original SVG designs that evoke the competition
//   through colour and shape only.
//
//   PL  — purple/lion motif hex
//   CL  — navy/gold star
//   PD  — orange/red geometric La Liga shape
//   BL1 — red/white Bundesliga circle
//   SA  — black/blue Serie A shield
//
// ACTIVE STATE:
//   useLocation() from React Router returns the current URL path.
//   We compare path to each link's href to apply active styling.
//   This is the standard pattern — no extra state needed.
//
// RESPONSIVE BEHAVIOUR:
//   On mobile (< md breakpoint) the competition links collapse.
//   Only the wordmark and pipeline button remain visible.
//   A hamburger menu is not implemented — acceptable for a dev tool.

import { Link, useLocation } from 'react-router-dom'
import PipelineButton from './PipelineButton'

// ── Competition badge SVGs ────────────────────────────────────────────────
// Each badge is a small 24×24 SVG. They use competition colours but are
// original geometric designs — not reproductions of official logos.

function PLBadge() {
  // Purple hexagon — Premier League colour palette
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <polygon
        points="10,1 18,5.5 18,14.5 10,19 2,14.5 2,5.5"
        fill="#3d195b"
        stroke="#7b2d8b"
        strokeWidth="1.5"
      />
      <polygon
        points="10,4 15.5,7 15.5,13 10,16 4.5,13 4.5,7"
        fill="none"
        stroke="#00ff85"
        strokeWidth="0.8"
        opacity="0.6"
      />
    </svg>
  )
}

function CLBadge() {
  // Navy circle with gold star — Champions League colours
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <circle cx="10" cy="10" r="9" fill="#001a4e" stroke="#c9a84c" strokeWidth="1.2"/>
      {/* 8-pointed star */}
      <polygon
        points="10,3 11.2,8 16,7 12.5,10.5 16,14 11.2,12 10,17 8.8,12 4,14 7.5,10.5 4,7 8.8,8"
        fill="#c9a84c"
        opacity="0.9"
      />
    </svg>
  )
}

function LaLigaBadge() {
  // Orange/red geometric — La Liga colours
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <rect x="1" y="1" width="18" height="18" rx="3" fill="#ee8000" />
      <rect x="4" y="4" width="12" height="12" rx="1.5" fill="none" stroke="#ffffff" strokeWidth="1.2"/>
      <line x1="10" y1="4" x2="10" y2="16" stroke="#ffffff" strokeWidth="1.2" opacity="0.6"/>
    </svg>
  )
}

function BundesligaBadge() {
  // Red circle — Bundesliga colours
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <circle cx="10" cy="10" r="9" fill="#d20515" stroke="#ffffff" strokeWidth="1.2"/>
      <circle cx="10" cy="10" r="5" fill="none" stroke="#ffffff" strokeWidth="1.2" opacity="0.7"/>
      <circle cx="10" cy="10" r="2" fill="#ffffff" opacity="0.9"/>
    </svg>
  )
}

function SerieABadge() {
  // Black/blue shield — Serie A colours
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <path
        d="M10 1 L18 4 L18 12 Q18 17 10 19 Q2 17 2 12 L2 4 Z"
        fill="#1a1a2e"
        stroke="#003399"
        strokeWidth="1.2"
      />
      <path
        d="M10 4 L15 6.5 L15 12 Q15 15.5 10 17 Q5 15.5 5 12 L5 6.5 Z"
        fill="none"
        stroke="#0066cc"
        strokeWidth="0.8"
        opacity="0.7"
      />
    </svg>
  )
}

// ── Competition nav links config ──────────────────────────────────────────

const COMPETITION_LINKS = [
  { href: '/',                 label: 'PL',  Badge: PLBadge,         title: 'Premier League'        },
  { href: '/champions-league', label: 'UCL', Badge: CLBadge,         title: 'Champions League'      },
  { href: '/la-liga',          label: 'PD',  Badge: LaLigaBadge,     title: 'La Liga'               },
  { href: '/bundesliga',       label: 'BL1', Badge: BundesligaBadge, title: 'Bundesliga'            },
  { href: '/serie-a',          label: 'SA',  Badge: SerieABadge,     title: 'Serie A'               },
]

// ── Navbar component ──────────────────────────────────────────────────────

function Navbar() {
  // useLocation() returns the current URL. We use pathname to determine
  // which nav link is active. No extra state — React Router handles it.
  const { pathname } = useLocation()

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-surface border-b border-bdr">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between gap-6">

        {/* ── Wordmark ── */}
        <Link to="/" className="flex items-center gap-3 shrink-0">
          <div>
            <span className="font-display text-2xl text-textprimary tracking-wider">
              FREEKICK
            </span>
            <span className="block text-xs text-fkgreenbright -mt-1 tracking-widest uppercase font-condensed">
              Match Intelligence
            </span>
          </div>
        </Link>

        {/* ── Competition links — hidden on mobile ── */}
        {/*
          hidden md:flex — Tailwind responsive prefix.
          On screens < 768px (md breakpoint), display:none.
          On screens >= 768px, display:flex.
          This prevents the navbar overflowing on small screens.
        */}
        <div className="hidden md:flex items-center gap-1">
          {COMPETITION_LINKS.map(({ href, label, Badge, title }) => {
            // Active if pathname exactly matches (home) or starts with (sub-routes)
            const isActive = href === '/'
              ? pathname === '/'
              : pathname.startsWith(href)

            return (
              <Link
                key={href}
                to={href}
                title={title}
                className={`
                  flex items-center gap-2 px-3 py-1.5 rounded
                  font-condensed text-xs font-bold tracking-widest uppercase
                  transition-colors duration-150
                  ${isActive
                    ? 'bg-surface3 text-textprimary border border-bdr'
                    : 'text-textsecondary hover:text-textprimary hover:bg-surface2'
                  }
                `}
              >
                <Badge />
                <span>{label}</span>
              </Link>
            )
          })}
        </div>

        {/* ── Pipeline button ── */}
        <div className="shrink-0">
          <PipelineButton />
        </div>

      </div>
    </nav>
  )
}

export default Navbar

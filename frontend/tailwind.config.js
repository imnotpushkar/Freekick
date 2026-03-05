/** @type {import('tailwindcss').Config} */
export default {
  // content: tells Tailwind WHERE to look for class names.
  // Tailwind scans these files at build time and only includes
  // CSS for classes it actually finds. This keeps the final
  // CSS bundle small — unused classes are never generated.
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",  // ** = any subdirectory, *.{} = any of these extensions
  ],
  theme: {
    extend: {
      // extend lets you ADD to Tailwind's defaults without replacing them.
      // We define our own design tokens here as CSS custom properties.
      colors: {
        pitch: {
          950: '#0a0f0a',   // near-black green — main background
          900: '#0d1410',   // dark green — card backgrounds
          800: '#152018',   // slightly lighter — borders, hover states
        },
        grass: {
          400: '#4ade80',   // bright green — primary accent, scores
          500: '#22c55e',   // medium green — secondary accent
        },
        chalk: {
          100: '#f0f4f0',   // near-white — primary text
          400: '#9ca89c',   // muted — secondary text, dates
        },
        card: {
          DEFAULT: '#121a12',  // card base background
          hover: '#1a241a',    // card hover state
        }
      },
      fontFamily: {
        // We use two fonts:
        // - 'Bebas Neue': condensed display font for scores, headings — football scoreboard feel
        // - 'DM Sans': clean, modern body font — readable at small sizes
        display: ['Bebas Neue', 'sans-serif'],
        body: ['DM Sans', 'sans-serif'],
      },
    },
  },
  plugins: [],
}

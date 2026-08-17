/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        forge: {
          50: 'var(--pf-forge-50)',
          100: 'var(--pf-forge-100)',
          200: 'var(--pf-forge-200)',
          300: '#f8a471',
          400: '#f47538',
          500: 'var(--pf-forge-500)',
          600: 'var(--pf-forge-600)',
          700: 'var(--pf-forge-700)',
          800: '#962f14',
          900: '#7a2914',
        },
        ink: {
          DEFAULT: 'var(--pf-ink-900)',
          50: '#f6f6f6',
          100: '#e7e7e7',
          200: '#d1d1d1',
          300: '#b0b0b0',
          400: 'var(--pf-ink-400)',
          500: 'var(--pf-ink-500)',
          600: '#5d5d5d',
          700: '#4f4f4f',
          800: '#454545',
          900: 'var(--pf-ink-900)',
          950: '#0a0a0a',
        },
        canvas: {
          DEFAULT: 'var(--pf-canvas)',
          border: 'var(--pf-canvas-border)',
        },
      },
      fontFamily: {
        sans: [
          'Plus Jakarta Sans',
          'system-ui',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
      },
      boxShadow: {
        card: '0 1px 3px 0 rgb(0 0 0 / 0.04), 0 1px 2px -1px rgb(0 0 0 / 0.04)',
        'card-hover': '0 4px 12px -2px rgb(0 0 0 / 0.08), 0 2px 4px -2px rgb(0 0 0 / 0.04)',
      },
    },
  },
  plugins: [],
}

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
          300: 'var(--pf-forge-300)',
          400: 'var(--pf-forge-400)',
          500: 'var(--pf-forge-500)',
          600: 'var(--pf-forge-600)',
          700: 'var(--pf-forge-700)',
          800: 'var(--pf-forge-800)',
          900: 'var(--pf-forge-900)',
        },
        ink: {
          DEFAULT: 'var(--pf-ink-900)',
          50: '#f4f4f5',
          100: '#e8e8ea',
          200: '#d4d4d8',
          300: '#b0b0b8',
          400: 'var(--pf-ink-400)',
          500: 'var(--pf-ink-500)',
          600: '#5d5e66',
          700: '#4a4b52',
          800: '#2e2f36',
          900: 'var(--pf-ink-900)',
          950: '#0B0D14',
        },
        canvas: {
          DEFAULT: 'var(--pf-canvas)',
          border: 'var(--pf-canvas-border)',
        },
        signal: {
          50: 'var(--po-signal-50)',
          100: 'var(--po-signal-100)',
          500: '#406BFF',
          600: 'var(--po-signal-600)',
        },
        moss: {
          50: 'var(--po-moss-50)',
          500: '#91B89A',
          600: 'var(--po-moss-600)',
        },
        midnight: {
          DEFAULT: 'var(--po-midnight)',
          elevated: 'var(--po-midnight-elevated)',
        },
        paper: {
          DEFAULT: 'var(--po-paper)',
          elevated: 'var(--po-paper-elevated)',
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
      fontSize: {
        'fluid-xs': 'var(--po-text-xs)',
        'fluid-sm': 'var(--po-text-sm)',
        'fluid-base': 'var(--po-text-base)',
        'fluid-lg': 'var(--po-text-lg)',
        'fluid-xl': 'var(--po-text-xl)',
        'fluid-2xl': 'var(--po-text-2xl)',
        'fluid-3xl': 'var(--po-text-3xl)',
        'fluid-4xl': 'var(--po-text-4xl)',
        'fluid-5xl': 'var(--po-text-5xl)',
      },
      boxShadow: {
        card: '0 1px 3px 0 rgb(11 13 20 / 0.04), 0 1px 2px -1px rgb(11 13 20 / 0.04)',
        'card-hover': '0 4px 12px -2px rgb(11 13 20 / 0.08), 0 2px 4px -2px rgb(11 13 20 / 0.04)',
        signal: '0 0 0 3px rgb(64 107 255 / 0.15)',
      },
    },
  },
  plugins: [],
}

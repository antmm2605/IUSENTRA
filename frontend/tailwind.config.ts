import type { Config } from 'tailwindcss'
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: { extend: { colors: { iusentra: { navy: 'var(--iu-navy-950)', blue: 'var(--iu-blue-600)', gold: 'var(--iu-gold-500)' } } } },
  plugins: []
} satisfies Config

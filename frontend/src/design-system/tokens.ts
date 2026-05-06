export const iusentraTokens = {
  color: {
    navy950: '#071329', navy900: '#0b1b35', navy800: '#102a4c',
    blue700: '#1d4ed8', blue600: '#2563eb', blue500: '#2f80ed',
    gold500: '#d4a017', danger500: '#ef4444', warning500: '#f59e0b',
    success500: '#10b981', purple500: '#a855f7',
    slate700: '#334155', slate600: '#475569', slate500: '#64748b',
    slate300: '#cbd5e1', slate100: '#f1f5f9',
    canvas: 'oklch(97% 0.008 255)', surface: 'oklch(99% 0.004 255 / .94)',
    border: 'rgba(15,23,42,.09)'
  },
  typography: {
    family: 'Inter, ui-sans-serif, system-ui, sans-serif',
    xs: '12px', sm: '13px', md: '14px', lg: '18px', xl: '28px'
  },
  spacing: { 1: '4px', 2: '8px', 3: '12px', 4: '16px', 5: '20px', 6: '24px' },
  radius: { sm: '8px', md: '10px', lg: '12px', xl: '16px', pill: '999px' },
  layout: { sidebar: '292px', topbar: '76px', bottomnav: '72px' },
  shadow: {
    soft: '0 10px 30px rgba(15,23,42,.06)',
    card: '0 18px 45px rgba(15,23,42,.08)',
    sidebar: '18px 0 42px rgba(2,6,23,.28)',
    drawer: '0 24px 80px rgba(15,23,42,.32)'
  }
} as const

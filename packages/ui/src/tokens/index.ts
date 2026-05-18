export const iusentraTokens = {
  color: {
    background: '#F6F7F9',
    surface: '#FFFFFF',
    surfaceSubtle: '#F1F5F9',
    foreground: '#111827',
    muted: '#64748B',
    border: '#E2E8F0',
    primary: '#1E3A8A',
    primaryActive: '#1D4ED8',
    accent: '#B08968',
    success: '#15803D',
    warning: '#B45309',
    danger: '#B91C1C',
    info: '#0369A1',
  },
  radius: {
    card: '8px',
    control: '8px',
  },
  spacing: {
    xs: '0.25rem',
    sm: '0.5rem',
    md: '0.75rem',
    lg: '1rem',
    xl: '1.5rem',
  },
} as const

export type IusentraTokens = typeof iusentraTokens

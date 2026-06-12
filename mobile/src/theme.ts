export const theme = {
  bg: { base: '#0a0a0c', surface: '#111114', input: '#17171c' },
  border: { subtle: '#26262e', strong: '#3a3a44' },
  fg: { primary: '#f5f5f7', muted: '#a1a1aa', faint: '#6b6b75' },
  accent: '#e31937',
  accentSoft: '#3a151b',
  ok: '#3ddc97',
  warn: '#f4b942',
  space: { xs: 4, sm: 8, md: 12, lg: 16, xl: 20, '2xl': 24, '3xl': 32, '4xl': 48 } as const,
  size: { xs: 12, sm: 13, base: 15, lg: 20, xl: 32 } as const,
  radius: { sm: 6, md: 8, lg: 12 } as const,
} as const;

export type Theme = typeof theme;

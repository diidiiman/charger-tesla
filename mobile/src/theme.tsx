import React, { createContext, useContext, useEffect, useState } from 'react';
import { useColorScheme } from 'react-native';
import { themePreference } from './storage';

const shared = {
  accent: '#e31937',
  accentSoft: '#3a151b', // Needs adjustment for light theme? Actually let's use rgba or separate it
  ok: '#3ddc97',
  warn: '#f4b942',
  space: { xs: 4, sm: 8, md: 12, lg: 16, xl: 20, '2xl': 24, '3xl': 32, '4xl': 48 } as const,
  size: { xs: 12, sm: 13, base: 15, lg: 20, xl: 32 } as const,
  radius: { sm: 6, md: 8, lg: 12 } as const,
} as const;

export const darkTheme = {
  ...shared,
  mode: 'dark' as const,
  bg: { base: '#0a0a0c', surface: '#111114', input: '#17171c' },
  border: { subtle: '#26262e', strong: '#3a3a44' },
  fg: { primary: '#f5f5f7', muted: '#a1a1aa', faint: '#6b6b75' },
  accentSoft: '#3a151b',
};

export const lightTheme = {
  ...shared,
  mode: 'light' as const,
  bg: { base: '#f5f5f7', surface: '#ffffff', input: '#e5e5ea' },
  border: { subtle: '#d1d1d6', strong: '#c7c7cc' },
  fg: { primary: '#1c1c1e', muted: '#8e8e93', faint: '#aeaeb2' },
  accentSoft: '#fde8eb',
};

export type Theme = typeof darkTheme | typeof lightTheme;

type ThemeContextType = {
  theme: Theme;
  themeMode: 'system' | 'light' | 'dark';
  setThemeMode: (mode: 'system' | 'light' | 'dark') => Promise<void>;
};

const ThemeContext = createContext<ThemeContextType | null>(null);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const systemColorScheme = useColorScheme();
  const [themeMode, setThemeModeState] = useState<'system' | 'light' | 'dark'>('system');

  useEffect(() => {
    themePreference.get().then((pref) => {
      if (pref) setThemeModeState(pref);
    });
  }, []);

  const setThemeMode = async (mode: 'system' | 'light' | 'dark') => {
    await themePreference.set(mode);
    setThemeModeState(mode);
  };

  const isDark = themeMode === 'dark' || (themeMode === 'system' && systemColorScheme === 'dark');
  const theme = isDark ? darkTheme : lightTheme;

  return (
    <ThemeContext.Provider value={{ theme, themeMode, setThemeMode }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}

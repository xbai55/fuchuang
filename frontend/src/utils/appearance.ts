import { storage } from './storage';

export type ThemeMode = 'dark' | 'light' | 'system';
export type FontSizeMode = 'small' | 'medium' | 'large';

export interface AppearanceSettings {
  theme: ThemeMode;
  fontSize: FontSizeMode;
  privacyMode: boolean;
}

const normalizeTheme = (value?: string | null): ThemeMode => {
  if (value === 'light' || value === 'system') {
    return value;
  }
  return 'dark';
};

const normalizeFontSize = (value?: string | null): FontSizeMode => {
  if (value === 'small' || value === 'large') {
    return value;
  }
  return 'medium';
};

export const getAppearanceSettings = (): AppearanceSettings => {
  const currentUser = storage.getUser();

  return {
    theme: normalizeTheme(currentUser?.theme),
    fontSize: normalizeFontSize(currentUser?.font_size),
    privacyMode: currentUser?.privacy_mode ?? false,
  };
};

export const resolveDarkMode = (themeMode: ThemeMode): boolean => {
  if (themeMode === 'system') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  }
  return themeMode === 'dark';
};

export const applyAppearance = (settings: AppearanceSettings): boolean => {
  const isDark = resolveDarkMode(settings.theme);
  const root = document.documentElement;

  root.classList.toggle('theme-dark', isDark);
  root.classList.toggle('theme-light', !isDark);
  root.classList.remove('font-size-small', 'font-size-medium', 'font-size-large');
  root.classList.add(`font-size-${settings.fontSize}`);
  root.classList.toggle('privacy-mode-on', settings.privacyMode);
  root.style.colorScheme = isDark ? 'dark' : 'light';

  return isDark;
};

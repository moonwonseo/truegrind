/**
 * themeStore.ts — Light/dark theme management with localStorage persistence.
 */

const STORAGE_KEY = 'tg-theme';

export type Theme = 'light' | 'dark';

let _theme = $state<Theme>('light');

export function getTheme(): Theme {
  return _theme;
}

export function initTheme() {
  if (typeof localStorage === 'undefined' || typeof document === 'undefined') return;
  const stored = localStorage.getItem(STORAGE_KEY);
  _theme = (stored === 'dark') ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', _theme);
}

export function toggleTheme() {
  _theme = _theme === 'light' ? 'dark' : 'light';
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(STORAGE_KEY, _theme);
  }
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', _theme);
  }
}

export function setTheme(theme: Theme) {
  _theme = theme;
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(STORAGE_KEY, _theme);
  }
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', _theme);
  }
}

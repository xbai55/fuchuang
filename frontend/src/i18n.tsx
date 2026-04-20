import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { storage } from './utils/storage';
import { APP_NAME, APP_NAME_EN } from './utils/brand';

export type Language = 'zh-CN' | 'en-US';

interface I18nContextValue {
  language: Language;
  isZh: boolean;
  setLanguage: (language: Language) => void;
}

const LANGUAGE_KEY = 'ui_language';

const I18nContext = createContext<I18nContextValue | null>(null);

const normalizeLanguage = (language?: string | null): Language => {
  if (language === 'en-US' || language?.toLowerCase().startsWith('en')) {
    return 'en-US';
  }
  return 'zh-CN';
};

const getInitialLanguage = (): Language => {
  const savedLanguage = localStorage.getItem(LANGUAGE_KEY);
  if (savedLanguage) {
    return normalizeLanguage(savedLanguage);
  }

  const currentUser = storage.getUser();
  if (currentUser?.language) {
    return normalizeLanguage(currentUser.language);
  }

  return normalizeLanguage(navigator.language);
};

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState<Language>(getInitialLanguage);

  useEffect(() => {
    localStorage.setItem(LANGUAGE_KEY, language);
    document.documentElement.lang = language;
    document.title = language === 'zh-CN' ? APP_NAME : APP_NAME_EN;

    const currentUser = storage.getUser();
    if (currentUser && currentUser.language !== language) {
      storage.setUser({ ...currentUser, language });
    }
  }, [language]);

  const value = useMemo<I18nContextValue>(
    () => ({
      language,
      isZh: language === 'zh-CN',
      setLanguage: setLanguageState,
    }),
    [language],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useI18n must be used within I18nProvider');
  }
  return context;
}

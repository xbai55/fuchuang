import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Button, ConfigProvider, theme, App as AntApp } from 'antd';
import { useCallback, useEffect, useState } from 'react';
import Login from './pages/Login';
import Register from './pages/Register';
import Home from './pages/Home';
import SettingsPage from './pages/SettingsPage';
import { storage } from './utils/storage';
import { I18nProvider, useI18n } from './i18n';
import { applyAppearance, getAppearanceSettings } from './utils/appearance';

const { defaultAlgorithm, darkAlgorithm } = theme;
const GLOBAL_MESSAGE_TOP = 88;

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  return storage.isAuthenticated() ? <>{children}</> : <Navigate to="/login" replace />;
}

function LanguageSwitcher() {
  const { language, setLanguage } = useI18n();

  return (
    <div className="card-dark fixed right-4 top-4 z-[1100] rounded-lg p-1 backdrop-blur">
      <div className="flex gap-1">
        <Button
          size="small"
          type={language === 'zh-CN' ? 'primary' : 'default'}
          onClick={() => setLanguage('zh-CN')}
        >
          中文
        </Button>
        <Button
          size="small"
          type={language === 'en-US' ? 'primary' : 'default'}
          onClick={() => setLanguage('en-US')}
        >
          EN
        </Button>
      </div>
    </div>
  );
}

function App() {
  const [isDark, setIsDark] = useState(() => applyAppearance(getAppearanceSettings()));

  const syncAppearance = useCallback(() => {
    setIsDark(applyAppearance(getAppearanceSettings()));
  }, []);

  useEffect(() => {
    syncAppearance();
  }, [syncAppearance]);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleSystemThemeChange = () => {
      if (getAppearanceSettings().theme === 'system') {
        syncAppearance();
      }
    };

    const handleAppearanceChange = () => {
      syncAppearance();
    };

    mediaQuery.addEventListener('change', handleSystemThemeChange);
    window.addEventListener('storage', handleAppearanceChange);
    window.addEventListener('appearance-changed', handleAppearanceChange as EventListener);

    return () => {
      mediaQuery.removeEventListener('change', handleSystemThemeChange);
      window.removeEventListener('storage', handleAppearanceChange);
      window.removeEventListener('appearance-changed', handleAppearanceChange as EventListener);
    };
  }, [syncAppearance]);

  return (
    <I18nProvider>
      <ConfigProvider
        theme={{
          algorithm: isDark ? darkAlgorithm : defaultAlgorithm,
          token: {
            colorPrimary: '#6366f1',
            colorInfo: '#6366f1',
          },
        }}
      >
        <AntApp
          message={{
            top: GLOBAL_MESSAGE_TOP,
            maxCount: 2,
            duration: 2.2,
          }}
          notification={{
            placement: 'bottomRight',
            duration: 3,
            maxCount: 3,
          }}
        >
          <LanguageSwitcher />
          <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <Home />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings"
                element={
                  <ProtectedRoute>
                    <SettingsPage onBack={() => window.history.back()} />
                  </ProtectedRoute>
                }
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </AntApp>
      </ConfigProvider>
    </I18nProvider>
  );
}

export default App;

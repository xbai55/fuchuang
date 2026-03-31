import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, theme, App as AntApp } from 'antd';
import { useState, useEffect } from 'react';
import Login from './pages/Login';
import Register from './pages/Register';
import Home from './pages/Home';
import SettingsPage from './pages/SettingsPage';
import { storage } from './utils/storage';

const { defaultAlgorithm, darkAlgorithm } = theme;

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  return storage.isAuthenticated() ? <>{children}</> : <Navigate to="/login" replace />;
}

function App() {
  const [isDark, setIsDark] = useState(true);

  useEffect(() => {
    // 加载用户主题设置
    const currentUser = storage.getUser();
    if (currentUser) {
      const userTheme = currentUser.theme || 'dark';
      if (userTheme === 'system') {
        // 检测系统主题
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        setIsDark(prefersDark);
      } else {
        setIsDark(userTheme === 'dark');
      }
    }

    // 监听系统主题变化
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (e: MediaQueryListEvent) => {
      const currentUser = storage.getUser();
      if (currentUser?.theme === 'system') {
        setIsDark(e.matches);
      }
    };
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  // 监听存储变化，实现主题切换
  useEffect(() => {
    const handleStorageChange = () => {
      const currentUser = storage.getUser();
      if (currentUser) {
        const userTheme = currentUser.theme || 'dark';
        if (userTheme === 'system') {
          const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
          setIsDark(prefersDark);
        } else {
          setIsDark(userTheme === 'dark');
        }
      }
    };

    // 监听自定义主题变更事件（来自 SettingsPage）
    const handleThemeChange = (e: CustomEvent) => {
      const newTheme = e.detail;
      if (newTheme === 'system') {
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        setIsDark(prefersDark);
      } else {
        setIsDark(newTheme === 'dark');
      }
    };

    window.addEventListener('storage', handleStorageChange);
    window.addEventListener('theme-changed', handleThemeChange as EventListener);
    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('theme-changed', handleThemeChange as EventListener);
    };
  }, []);

  return (
    <ConfigProvider
      theme={{
        algorithm: isDark ? darkAlgorithm : defaultAlgorithm,
        token: {
          colorPrimary: '#6366f1',
          colorInfo: '#6366f1',
        },
      }}
    >
      <AntApp>
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
  );
}

export default App;

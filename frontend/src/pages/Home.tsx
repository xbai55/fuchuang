import { useState } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { Layout, ConfigProvider, theme } from 'antd';
import ChatPage from './ChatPage';
import ContactsPage from './ContactsPage';
import Sidebar from '../components/Sidebar';
import { storage } from '../utils/storage';

const { defaultAlgorithm, darkAlgorithm } = theme;

export default function Home() {
  const navigate = useNavigate();
  const [currentPage, setCurrentPage] = useState<'chat' | 'contacts'>('chat');

  // 检查登录状态
  if (!storage.isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }

  return (
    <ConfigProvider
      theme={{
        algorithm: darkAlgorithm,
        token: {
          colorPrimary: '#6366f1',
          colorInfo: '#6366f1',
        },
        components: {
          Menu: {
            darkItemSelectedBg: '#1e1e38',
          },
        },
      }}
    >
      {currentPage === 'chat' && (
        <ChatPage />
      )}
      {currentPage === 'contacts' && (
        <ContactsPage onPageChange={setCurrentPage} />
      )}
    </ConfigProvider>
  );
}

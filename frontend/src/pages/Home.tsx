import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import ChatPage from './ChatPage';
import ContactsPage from './ContactsPage';
import Sidebar from '../components/Sidebar';
import { storage } from '../utils/storage';

export default function Home() {
  const [currentPage, setCurrentPage] = useState<'chat' | 'contacts'>('chat');

  // 检查登录状态
  if (!storage.isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="flex">
      <Sidebar currentPage={currentPage} onPageChange={setCurrentPage} />
      {currentPage === 'chat' && (
        <ChatPage />
      )}
      {currentPage === 'contacts' && (
        <ContactsPage onPageChange={setCurrentPage} />
      )}
    </div>
  );
}

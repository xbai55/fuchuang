import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Avatar, Dropdown, Layout, Menu } from 'antd';
import {
  ContactsOutlined,
  LogoutOutlined,
  MessageOutlined,
  SettingOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { storage } from '../utils/storage';
import { useI18n } from '../i18n';
import { maskEmail, maskUsername, USER_SETTINGS_CHANGED_EVENT } from '../utils/privacy';
import type { User } from '../types';

const { Sider } = Layout;

interface SidebarProps {
  currentPage: 'chat' | 'contacts';
  onPageChange: (page: 'chat' | 'contacts') => void;
  onContactAdd?: () => void;
}

export default function Sidebar({ currentPage, onPageChange }: SidebarProps) {
  const navigate = useNavigate();
  const { isZh } = useI18n();
  const [user, setUser] = useState<User | null>(storage.getUser());
  const [menuTheme, setMenuTheme] = useState<'light' | 'dark'>(() => {
    return document.documentElement.classList.contains('theme-light') ? 'light' : 'dark';
  });

  const t = (zh: string, en: string) => (isZh ? zh : en);

  useEffect(() => {
    const syncUser = () => {
      setUser(storage.getUser());
    };

    const syncTheme = () => {
      setMenuTheme(document.documentElement.classList.contains('theme-light') ? 'light' : 'dark');
    };

    syncTheme();
    syncUser();

    window.addEventListener('storage', syncUser);
    window.addEventListener(USER_SETTINGS_CHANGED_EVENT, syncUser);
    window.addEventListener('appearance-changed', syncTheme);

    return () => {
      window.removeEventListener('storage', syncUser);
      window.removeEventListener(USER_SETTINGS_CHANGED_EVENT, syncUser);
      window.removeEventListener('appearance-changed', syncTheme);
    };
  }, []);

  const privacyMode = user?.privacy_mode ?? false;
  const displayUsername = user?.username
    ? (privacyMode ? maskUsername(user.username) : user.username)
    : t('访客', 'Guest');
  const displayEmail = user?.email
    ? (privacyMode ? maskEmail(user.email) : user.email)
    : t('未设置邮箱', 'No email');

  const handleLogout = () => {
    storage.clear();
    navigate('/login');
  };

  const menuItems = [
    {
      key: 'chat',
      icon: <MessageOutlined />,
      label: t('风险识别对话', 'Risk Analysis Chat'),
      onClick: () => onPageChange('chat'),
    },
    {
      key: 'contacts',
      icon: <ContactsOutlined />,
      label: t('紧急联系人', 'Emergency Contacts'),
      onClick: () => onPageChange('contacts'),
    },
  ];

  const userMenuItems = [
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: t('设置', 'Settings'),
      onClick: () => navigate('/settings'),
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: t('退出登录', 'Log Out'),
      onClick: handleLogout,
    },
  ];

  return (
    <Sider
      width={260}
      className="bg-darker border-r border-gray-800"
      style={{ overflow: 'auto', height: '100vh', position: 'fixed', left: 0, top: 0 }}
    >
      <div className="p-6">
        <div className="text-xs uppercase tracking-[0.3em] text-gray-500">{t('守护', 'GUARD')}</div>
        <h1 className="mt-2 text-2xl font-bold bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
          {t('反诈预警', 'Anti-fraud Alert')}
        </h1>
      </div>

      <Menu
        theme={menuTheme}
        mode="inline"
        selectedKeys={[currentPage]}
        items={menuItems}
        className="bg-transparent border-0"
      />

      <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-800">
        <Dropdown
          menu={{ items: userMenuItems }}
          placement="topLeft"
          trigger={['click']}
        >
          <div className="flex items-center gap-3 p-2 rounded-lg hover:bg-dark-lighter cursor-pointer transition-all">
            <Avatar icon={<UserOutlined />} className="bg-primary" />
            <div className="flex-1 min-w-0">
              <div className="font-medium truncate text-white">{displayUsername}</div>
              <div className="text-xs text-gray-400 truncate">{displayEmail}</div>
            </div>
          </div>
        </Dropdown>
      </div>
    </Sider>
  );
}

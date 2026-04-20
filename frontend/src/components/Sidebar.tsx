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
import { APP_NAME, APP_NAME_EN, APP_TAGLINE, APP_TAGLINE_EN, BRAND_LOGO_SRC } from '../utils/brand';
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
  const brandName = t(APP_NAME, APP_NAME_EN);
  const brandTagline = t(APP_TAGLINE, APP_TAGLINE_EN);

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
      label: t('风险识别', 'Risk Analysis'),
      onClick: () => onPageChange('chat'),
    },
    {
      key: 'contacts',
      icon: <ContactsOutlined />,
      label: t('\u53ef\u4fe1\u8054\u7cfb\u4eba', 'Trusted Contacts'),
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
      width={96}
      className="app-sidebar agent-sidebar bg-darker"
      style={{ overflow: 'auto', height: '100vh', position: 'fixed', left: 0, top: 0 }}
    >
      <div className="agent-brand-block px-5 pb-6 pt-5">
        <div className="flex items-center gap-3">
          <div className="brand-logo h-11 w-11 rounded-lg">
            <img src={BRAND_LOGO_SRC} alt={brandName} />
          </div>
          <div className="agent-brand-text min-w-0">
            <div className="page-kicker">Tianshu</div>
            <h1 className="mt-1 truncate text-xl font-semibold text-white">{brandName}</h1>
          </div>
        </div>
        <p className="agent-brand-tagline mt-4 text-xs leading-5 text-gray-400">{brandTagline}</p>
      </div>

      <Menu
        theme={menuTheme}
        mode="inline"
        selectedKeys={[currentPage]}
        items={menuItems}
        className="bg-transparent border-0"
      />

      <div className="agent-sidebar-user absolute bottom-0 left-0 right-0 p-4">
        <Dropdown
          menu={{ items: userMenuItems }}
          placement="topLeft"
          trigger={['click']}
        >
          <div className="flex items-center gap-3 rounded-lg p-2 transition-all hover:bg-dark-lighter cursor-pointer">
            <Avatar icon={<UserOutlined />} className="sidebar-user-avatar" />
            <div className="agent-user-text flex-1 min-w-0">
              <div className="font-medium truncate text-white">{displayUsername}</div>
              <div className="text-xs text-gray-400 truncate">{displayEmail}</div>
            </div>
          </div>
        </Dropdown>
      </div>
    </Sider>
  );
}

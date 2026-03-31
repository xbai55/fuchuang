import { useState, useEffect } from 'react';
import { Layout, Menu, Avatar, Dropdown } from 'antd';
import {
  MessageOutlined,
  ContactsOutlined,
  UserOutlined,
  LogoutOutlined,
  SettingOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { storage } from '../utils/storage';
import type { User } from '../types';

const { Sider } = Layout;

interface SidebarProps {
  currentPage: 'chat' | 'contacts';
  onPageChange: (page: 'chat' | 'contacts') => void;
  onContactAdd?: () => void;
}

export default function Sidebar({ currentPage, onPageChange }: SidebarProps) {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const currentUser = storage.getUser();
    if (currentUser) {
      setUser(currentUser);
    }
  }, []);

  const handleLogout = () => {
    storage.clear();
    navigate('/login');
  };

  const handleSettings = () => {
    navigate('/settings');
  };

  const menuItems = [
    {
      key: 'chat',
      icon: <MessageOutlined />,
      label: '对话预警',
      onClick: () => onPageChange('chat'),
    },
    {
      key: 'contacts',
      icon: <ContactsOutlined />,
      label: '联系人设置',
      onClick: () => onPageChange('contacts'),
    },
  ];

  const userMenuItems = [
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: '设置中心',
      onClick: handleSettings,
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
    },
  ];

  return (
    <>
      <Sider
        width={260}
        className="bg-darker border-r border-gray-800"
        style={{ overflow: 'auto', height: '100vh', position: 'fixed', left: 0, top: 0 }}
      >
        <div className="p-6">
          <h1 className="text-2xl font-bold bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
            反诈预警
          </h1>
        </div>

        <Menu
          theme="dark"
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
                <div className="font-medium truncate">{user?.username}</div>
                <div className="text-xs text-gray-400 truncate">{user?.email}</div>
              </div>
            </div>
          </Dropdown>
        </div>
      </Sider>
    </>
  );
}

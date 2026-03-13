import { useState, useEffect } from 'react';
import { Layout, Menu, Button, Avatar, Dropdown, Modal, Form, Input, Select, message } from 'antd';
import {
  MessageOutlined,
  ContactsOutlined,
  UserOutlined,
  LogoutOutlined,
  SettingOutlined
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { authAPI } from '../services/api';
import { storage } from '../utils/storage';
import type { User } from '../types';
import type { ContactCreate } from '../types';
import { contactsAPI } from '../services/api';

const { Sider } = Layout;

interface SidebarProps {
  currentPage: 'chat' | 'contacts';
  onPageChange: (page: 'chat' | 'contacts') => void;
  onContactAdd?: () => void;
}

export default function Sidebar({ currentPage, onPageChange, onContactAdd }: SidebarProps) {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    const currentUser = storage.getUser();
    if (currentUser) {
      setUser(currentUser);
      form.setFieldsValue({
        user_role: currentUser.user_role,
        guardian_name: currentUser.guardian_name
      });
    }
  }, [form]);

  const handleProfileUpdate = async (values: any) => {
    try {
      const updatedUser = await authAPI.updateUser(values.user_role, values.guardian_name);
      storage.setUser(updatedUser);
      setUser(updatedUser);
      message.success('个人信息更新成功！');
      setIsProfileModalOpen(false);
    } catch (error) {
      message.error('更新失败，请稍后重试');
    }
  };

  const handleLogout = () => {
    storage.clear();
    navigate('/login');
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
      key: 'profile',
      icon: <SettingOutlined />,
      label: '个人信息',
      onClick: () => setIsProfileModalOpen(true),
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

      {/* 个人信息模态框 */}
      <Modal
        title="个人信息设置"
        open={isProfileModalOpen}
        onCancel={() => setIsProfileModalOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setIsProfileModalOpen(false)}>
            取消
          </Button>,
          <Button key="submit" type="primary" onClick={() => form.submit()}>
            保存
          </Button>,
        ]}
      >
        <Form
          form={form}
          onFinish={handleProfileUpdate}
          layout="vertical"
        >
          <Form.Item
            label="用户角色"
            name="user_role"
            tooltip="选择您的角色，系统将针对性地提供反诈建议"
          >
            <Select>
              <Select.Option value="general">通用用户</Select.Option>
              <Select.Option value="elderly">老年人</Select.Option>
              <Select.Option value="student">学生</Select.Option>
              <Select.Option value="finance">财会人员</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            label="监护人姓名"
            name="guardian_name"
            tooltip="高风险时系统会自动通知监护人"
          >
            <Input placeholder="请输入监护人姓名" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

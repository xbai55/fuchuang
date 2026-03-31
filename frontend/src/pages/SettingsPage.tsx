import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Form,
  Input,
  Select,
  Switch,
  Button,
  Divider,
  App,
  Space,
  Avatar,
  Typography,
  Row,
  Col,
  Modal,
  Alert,
  Radio,
} from 'antd';
import {
  UserOutlined,
  LockOutlined,
  BellOutlined,
  SettingOutlined,
  SafetyOutlined,
  LogoutOutlined,
  DeleteOutlined,
  MoonOutlined,
  SunOutlined,
  DesktopOutlined,
  ArrowLeftOutlined,
} from '@ant-design/icons';
import { storage } from '../utils/storage';
import { settingsAPI } from '../services/api';
import type { User, UserSettings, UserProfileUpdate, ChangePasswordRequest } from '../types';

const { Title, Text } = Typography;
const { Option } = Select;

interface SettingsPageProps {
  onBack: () => void;
}

export default function SettingsPage({ onBack }: SettingsPageProps) {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'profile' | 'appearance' | 'notifications' | 'security'>('profile');

  // 表单实例
  const [profileForm] = Form.useForm();
  const [passwordForm] = Form.useForm();

  // 本地状态
  const [theme, setTheme] = useState<'dark' | 'light' | 'system'>('dark');
  const [notifyEnabled, setNotifyEnabled] = useState(true);
  const [notifyHighRisk, setNotifyHighRisk] = useState(true);
  const [notifyGuardianAlert, setNotifyGuardianAlert] = useState(true);
  const [fontSize, setFontSize] = useState<'small' | 'medium' | 'large'>('medium');
  const [privacyMode, setPrivacyMode] = useState(false);

  useEffect(() => {
    loadUserSettings();
  }, []);

  const loadUserSettings = async () => {
    try {
      const currentUser = storage.getUser();
      if (currentUser) {
        setUser(currentUser);
        // 初始化表单值
        profileForm.setFieldsValue({
          username: currentUser.username,
          email: currentUser.email,
          user_role: currentUser.user_role,
          guardian_name: currentUser.guardian_name,
        });
        // 初始化设置状态
        setTheme(currentUser.theme || 'dark');
        setNotifyEnabled(currentUser.notify_enabled ?? true);
        setNotifyHighRisk(currentUser.notify_high_risk ?? true);
        setNotifyGuardianAlert(currentUser.notify_guardian_alert ?? true);
        setFontSize(currentUser.font_size || 'medium');
        setPrivacyMode(currentUser.privacy_mode ?? false);
      }
    } catch (error) {
      message.error('加载用户设置失败');
    }
  };

  // 更新主题
  const handleThemeChange = async (newTheme: 'dark' | 'light' | 'system') => {
    setTheme(newTheme);
    try {
      const updatedUser = await settingsAPI.updateSettings({ theme: newTheme });
      updateLocalUser(updatedUser);
      message.success('主题已更新');
      // 触发自定义事件通知 App.tsx 更新主题
      window.dispatchEvent(new CustomEvent('theme-changed', { detail: newTheme }));
    } catch (error) {
      message.error('主题更新失败');
    }
  };

  // 更新通知设置
  const handleNotifyChange = async (key: keyof UserSettings, value: boolean) => {
    if (key === 'notify_enabled') setNotifyEnabled(value);
    if (key === 'notify_high_risk') setNotifyHighRisk(value);
    if (key === 'notify_guardian_alert') setNotifyGuardianAlert(value);

    try {
      const updatedUser = await settingsAPI.updateSettings({ [key]: value });
      updateLocalUser(updatedUser);
    } catch (error) {
      message.error('通知设置更新失败');
    }
  };

  // 更新字体大小
  const handleFontSizeChange = async (size: 'small' | 'medium' | 'large') => {
    setFontSize(size);
    try {
      const updatedUser = await settingsAPI.updateSettings({ font_size: size });
      updateLocalUser(updatedUser);
      message.success('字体大小已更新');
    } catch (error) {
      message.error('字体大小更新失败');
    }
  };

  // 更新隐私模式
  const handlePrivacyModeChange = async (enabled: boolean) => {
    setPrivacyMode(enabled);
    try {
      const updatedUser = await settingsAPI.updateSettings({ privacy_mode: enabled });
      updateLocalUser(updatedUser);
      message.success(enabled ? '隐私模式已开启' : '隐私模式已关闭');
    } catch (error) {
      message.error('隐私模式设置失败');
    }
  };

  // 更新本地用户数据
  const updateLocalUser = (updatedUser: User) => {
    setUser(updatedUser);
    storage.setUser(updatedUser);
  };

  // 保存个人资料
  const handleSaveProfile = async (values: UserProfileUpdate) => {
    setLoading(true);
    try {
      const updatedUser = await settingsAPI.updateProfile(values);
      updateLocalUser(updatedUser);
      message.success('个人资料已更新');
    } catch (error: any) {
      message.error(error.response?.data?.detail || '更新失败');
    } finally {
      setLoading(false);
    }
  };

  // 修改密码
  const handleChangePassword = async (values: ChangePasswordRequest) => {
    if (values.new_password !== values.confirm_password) {
      message.error('两次输入的新密码不一致');
      return;
    }
    setLoading(true);
    try {
      await settingsAPI.changePassword({
        current_password: values.current_password,
        new_password: values.new_password,
      });
      message.success('密码修改成功');
      passwordForm.resetFields();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '密码修改失败');
    } finally {
      setLoading(false);
    }
  };

  // 退出登录
  const handleLogout = () => {
    Modal.confirm({
      title: '确认退出登录？',
      content: '退出后需要重新登录才能使用系统',
      okText: '确认退出',
      cancelText: '取消',
      onOk: () => {
        storage.clear();
        navigate('/login');
      },
    });
  };

  // 注销账号
  const handleDeleteAccount = () => {
    Modal.confirm({
      title: '⚠️ 确认注销账号？',
      content: (
        <div>
          <p>此操作将永久删除您的账号和所有数据，无法恢复！</p>
          <Alert
            message="注销后以下数据将被删除："
            description="
              • 个人资料和设置
              • 联系人列表
              • 聊天记录和历史
            "
            type="warning"
            showIcon
            style={{ marginTop: 16 }}
          />
        </div>
      ),
      okText: '确认注销',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await settingsAPI.deleteAccount();
          message.success('账号已注销');
          storage.clear();
          navigate('/login');
        } catch (error) {
          message.error('注销失败，请稍后重试');
        }
      },
    });
  };

  const menuItems = [
    { key: 'profile', icon: <UserOutlined />, label: '个人资料' },
    { key: 'appearance', icon: <SettingOutlined />, label: '外观设置' },
    { key: 'notifications', icon: <BellOutlined />, label: '通知管理' },
    { key: 'security', icon: <SafetyOutlined />, label: '安全设置' },
  ];

  return (
    <div className="min-h-screen bg-darker p-6">
      <div className="max-w-6xl mx-auto">
        {/* 头部 */}
        <div className="flex items-center gap-4 mb-6">
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={onBack}
            className="btn-secondary"
          >
            返回
          </Button>
          <Title level={3} className="!text-white !mb-0">
            设置中心
          </Title>
        </div>

        <Row gutter={24}>
          {/* 左侧菜单 */}
          <Col xs={24} lg={6}>
            <Card className="card-dark !border-gray-700" variant="borderless">
              <div className="flex items-center gap-3 mb-6 pb-4 border-b border-gray-700">
                <Avatar size={64} icon={<UserOutlined />} className="bg-primary" />
                <div>
                  <div className="font-semibold text-white">{user?.username}</div>
                  <div className="text-sm text-gray-400">{user?.email}</div>
                </div>
              </div>

              <Space direction="vertical" className="w-full">
                {menuItems.map((item) => (
                  <Button
                    key={item.key}
                    type={activeTab === item.key ? 'primary' : 'text'}
                    icon={item.icon}
                    onClick={() => setActiveTab(item.key as any)}
                    className={`w-full justify-start text-left ${
                      activeTab === item.key ? '' : 'text-gray-300 hover:text-white'
                    }`}
                  >
                    {item.label}
                  </Button>
                ))}

                <Divider className="!border-gray-700" />

                <Button
                  type="text"
                  icon={<LogoutOutlined />}
                  onClick={handleLogout}
                  className="w-full justify-start text-left text-yellow-400 hover:text-yellow-300"
                >
                  退出登录
                </Button>
              </Space>
            </Card>
          </Col>

          {/* 右侧内容 */}
          <Col xs={24} lg={18}>
            {/* 个人资料 */}
            {activeTab === 'profile' && (
              <Card
                title="个人资料"
                className="card-dark !border-gray-700"
                variant="borderless"
              >
                <Form
                  form={profileForm}
                  layout="vertical"
                  onFinish={handleSaveProfile}
                >
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item
                        label="用户名"
                        name="username"
                        rules={[
                          { required: true, message: '请输入用户名' },
                          { min: 3, message: '用户名至少3个字符' },
                        ]}
                      >
                        <Input
                          prefix={<UserOutlined />}
                          placeholder="用户名"
                          className="input-dark"
                        />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item
                        label="邮箱"
                        name="email"
                        rules={[
                          { required: true, message: '请输入邮箱' },
                          { type: 'email', message: '请输入有效的邮箱地址' },
                        ]}
                      >
                        <Input
                          prefix={<UserOutlined />}
                          placeholder="邮箱"
                          className="input-dark"
                        />
                      </Form.Item>
                    </Col>
                  </Row>

                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item
                        label="用户角色"
                        name="user_role"
                        tooltip="选择您的角色，系统将针对性地提供反诈建议"
                      >
                        <Select className="w-full">
                          <Option value="general">通用用户</Option>
                          <Option value="elderly">老年人</Option>
                          <Option value="student">学生</Option>
                          <Option value="finance">财会人员</Option>
                        </Select>
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item
                        label="监护人姓名"
                        name="guardian_name"
                        tooltip="高风险时系统会自动通知监护人"
                      >
                        <Input
                          placeholder="请输入监护人姓名"
                          className="input-dark"
                        />
                      </Form.Item>
                    </Col>
                  </Row>

                  <Form.Item>
                    <Button
                      type="primary"
                      htmlType="submit"
                      loading={loading}
                      className="btn-primary"
                    >
                      保存资料
                    </Button>
                  </Form.Item>
                </Form>
              </Card>
            )}

            {/* 外观设置 */}
            {activeTab === 'appearance' && (
              <Card
                title="外观设置"
                className="card-dark !border-gray-700"
                variant="borderless"
              >
                <div className="space-y-6">
                  <div>
                    <Text className="text-white block mb-3">主题模式</Text>
                    <Radio.Group
                      value={theme}
                      onChange={(e) => handleThemeChange(e.target.value)}
                      className="flex gap-4"
                    >
                      <Radio.Button value="dark" className="flex items-center gap-2">
                        <MoonOutlined /> 深色模式
                      </Radio.Button>
                      <Radio.Button value="light" className="flex items-center gap-2">
                        <SunOutlined /> 浅色模式
                      </Radio.Button>
                      <Radio.Button value="system" className="flex items-center gap-2">
                        <DesktopOutlined /> 跟随系统
                      </Radio.Button>
                    </Radio.Group>
                  </div>

                  <Divider className="!border-gray-700" />

                  <div>
                    <Text className="text-white block mb-3">字体大小</Text>
                    <Radio.Group
                      value={fontSize}
                      onChange={(e) => handleFontSizeChange(e.target.value)}
                    >
                      <Radio.Button value="small">小</Radio.Button>
                      <Radio.Button value="medium">中</Radio.Button>
                      <Radio.Button value="large">大</Radio.Button>
                    </Radio.Group>
                  </div>

                  <Divider className="!border-gray-700" />

                  <div className="flex items-center justify-between">
                    <div>
                      <Text className="text-white block">隐私模式</Text>
                      <Text className="text-gray-400 text-sm">
                        开启后，敏感信息将以模糊方式显示
                      </Text>
                    </div>
                    <Switch
                      checked={privacyMode}
                      onChange={handlePrivacyModeChange}
                      checkedChildren="开启"
                      unCheckedChildren="关闭"
                    />
                  </div>
                </div>
              </Card>
            )}

            {/* 通知管理 */}
            {activeTab === 'notifications' && (
              <Card
                title="通知管理"
                className="card-dark !border-gray-700"
                variant="borderless"
              >
                <div className="space-y-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <Text className="text-white block">启用通知</Text>
                      <Text className="text-gray-400 text-sm">
                        接收系统推送的各类通知消息
                      </Text>
                    </div>
                    <Switch
                      checked={notifyEnabled}
                      onChange={(v) => handleNotifyChange('notify_enabled', v)}
                      checkedChildren="开启"
                      unCheckedChildren="关闭"
                    />
                  </div>

                  <Divider className="!border-gray-700" />

                  <div className="flex items-center justify-between">
                    <div>
                      <Text className="text-white block">高风险提醒</Text>
                      <Text className="text-gray-400 text-sm">
                        检测到高风险诈骗时立即通知
                      </Text>
                    </div>
                    <Switch
                      checked={notifyHighRisk}
                      onChange={(v) => handleNotifyChange('notify_high_risk', v)}
                      disabled={!notifyEnabled}
                      checkedChildren="开启"
                      unCheckedChildren="关闭"
                    />
                  </div>

                  <Divider className="!border-gray-700" />

                  <div className="flex items-center justify-between">
                    <div>
                      <Text className="text-white block">监护人联动通知</Text>
                      <Text className="text-gray-400 text-sm">
                        高风险时同时通知监护人
                      </Text>
                    </div>
                    <Switch
                      checked={notifyGuardianAlert}
                      onChange={(v) => handleNotifyChange('notify_guardian_alert', v)}
                      disabled={!notifyEnabled}
                      checkedChildren="开启"
                      unCheckedChildren="关闭"
                    />
                  </div>
                </div>
              </Card>
            )}

            {/* 安全设置 */}
            {activeTab === 'security' && (
              <Card
                title="安全设置"
                className="card-dark !border-gray-700"
                variant="borderless"
              >
                <div className="space-y-6">
                  <div>
                    <Text className="text-white block mb-4">修改密码</Text>
                    <Form
                      form={passwordForm}
                      layout="vertical"
                      onFinish={handleChangePassword}
                    >
                      <Form.Item
                        label="当前密码"
                        name="current_password"
                        rules={[{ required: true, message: '请输入当前密码' }]}
                      >
                        <Input.Password
                          prefix={<LockOutlined />}
                          placeholder="当前密码"
                          className="input-dark"
                        />
                      </Form.Item>

                      <Form.Item
                        label="新密码"
                        name="new_password"
                        rules={[
                          { required: true, message: '请输入新密码' },
                          { min: 6, message: '密码至少6个字符' },
                        ]}
                      >
                        <Input.Password
                          prefix={<LockOutlined />}
                          placeholder="新密码"
                          className="input-dark"
                        />
                      </Form.Item>

                      <Form.Item
                        label="确认新密码"
                        name="confirm_password"
                        rules={[
                          { required: true, message: '请确认新密码' },
                        ]}
                      >
                        <Input.Password
                          prefix={<LockOutlined />}
                          placeholder="确认新密码"
                          className="input-dark"
                        />
                      </Form.Item>

                      <Form.Item>
                        <Button
                          type="primary"
                          htmlType="submit"
                          loading={loading}
                          className="btn-primary"
                        >
                          修改密码
                        </Button>
                      </Form.Item>
                    </Form>
                  </div>

                  <Divider className="!border-gray-700" />

                  <div className="flex items-center justify-between p-4 bg-red-900/20 rounded-lg border border-red-800">
                    <div>
                      <Text className="text-red-400 block font-medium">注销账号</Text>
                      <Text className="text-gray-400 text-sm">
                        此操作将永久删除您的账号和所有数据
                      </Text>
                    </div>
                    <Button
                      danger
                      icon={<DeleteOutlined />}
                      onClick={handleDeleteAccount}
                    >
                      注销账号
                    </Button>
                  </div>
                </div>
              </Card>
            )}
          </Col>
        </Row>
      </div>
    </div>
  );
}

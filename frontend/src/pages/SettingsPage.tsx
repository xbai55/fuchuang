import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  App,
  Button,
  Card,
  Col,
  Divider,
  Form,
  Input,
  Modal,
  Radio,
  Row,
  Select,
  Space,
  Switch,
  Typography,
} from 'antd';
import {
  ArrowLeftOutlined,
  DeleteOutlined,
  LockOutlined,
  LogoutOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { settingsAPI } from '../services/api';
import { useI18n } from '../i18n';
import { storage } from '../utils/storage';
import { notifyUserSettingsChanged } from '../utils/privacy';
import type { ChangePasswordRequest, User, UserProfileUpdate, UserSettings } from '../types';

const { Text, Title } = Typography;

interface SettingsPageProps {
  onBack: () => void;
}

type ApiError = {
  response?: {
    data?: {
      detail?: string;
      message?: string;
    };
  };
};

export default function SettingsPage({ onBack }: SettingsPageProps) {
  const { message } = App.useApp();
  const { isZh, setLanguage } = useI18n();
  const navigate = useNavigate();
  const [profileForm] = Form.useForm<UserProfileUpdate>();
  const [passwordForm] = Form.useForm<ChangePasswordRequest & { confirm_password: string }>();
  const [user, setUser] = useState<User | null>(storage.getUser());
  const [loading, setLoading] = useState(false);

  const t = (zh: string, en: string) => (isZh ? zh : en);

  const occupationOptions = [
    { value: 'student', label: t('学生', 'Student') },
    { value: 'enterprise_staff', label: t('企业职员', 'Enterprise Staff') },
    { value: 'self_employed', label: t('个体经营', 'Self-employed') },
    { value: 'retired_group', label: t('退休群体', 'Retired Group') },
    { value: 'public_officer', label: t('公职人员', 'Public Officer') },
    { value: 'finance_practitioner', label: t('金融从业者', 'Finance Practitioner') },
    { value: 'other', label: t('其他职业', 'Other Occupation') },
  ];

  const ageGroupOptions = [
    { value: 'child', label: t('儿童', 'Child') },
    { value: 'young_adult', label: t('青年', 'Young Adult') },
    { value: 'elderly', label: t('老年', 'Elderly') },
  ];

  const genderOptions = [
    { value: 'male', label: t('男', 'Male') },
    { value: 'female', label: t('女', 'Female') },
  ];

  const getErrorMessage = (error: unknown, fallback: string) => {
    const apiError = error as ApiError;
    return apiError.response?.data?.detail ?? apiError.response?.data?.message ?? fallback;
  };

  const updateLocalUser = (updatedUser: User) => {
    setUser(updatedUser);
    storage.setUser(updatedUser);
  };

  const loadSettings = async () => {
    setLoading(true);
    try {
      const settings = await settingsAPI.getSettings();
      updateLocalUser(settings);
      profileForm.setFieldsValue({
        username: settings.username,
        email: settings.email,
        user_role: settings.user_role,
        age_group: settings.age_group,
        gender: settings.gender,
        occupation: settings.occupation,
      });
    } catch (error) {
      message.error(getErrorMessage(error, t('加载设置失败', 'Failed to load settings')));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSettings();
  }, []);

  const dispatchAppearanceChanged = () => {
    window.dispatchEvent(new Event('appearance-changed'));
  };

  const updateSettings = async (patch: UserSettings, successText: string) => {
    try {
      const updatedUser = await settingsAPI.updateSettings(patch);
      updateLocalUser(updatedUser);
      notifyUserSettingsChanged();
      message.success(successText);
      if (patch.theme || patch.privacy_mode || patch.font_size) {
        dispatchAppearanceChanged();
      }
      if (patch.language) {
        setLanguage(patch.language);
      }
    } catch (error) {
      message.error(getErrorMessage(error, t('更新设置失败', 'Failed to update settings')));
    }
  };

  const handleSaveProfile = async (values: UserProfileUpdate) => {
    setLoading(true);
    try {
      const updatedUser = await settingsAPI.updateProfile(values);
      updateLocalUser(updatedUser);
      notifyUserSettingsChanged();
      message.success(t('资料已更新', 'Profile updated'));
    } catch (error) {
      message.error(getErrorMessage(error, t('更新资料失败', 'Failed to update profile')));
    } finally {
      setLoading(false);
    }
  };

  const handleChangePassword = async (values: ChangePasswordRequest & { confirm_password: string }) => {
    if (values.new_password !== values.confirm_password) {
      message.error(t('两次输入的密码不一致', 'Passwords do not match'));
      return;
    }

    setLoading(true);
    try {
      await settingsAPI.changePassword({
        current_password: values.current_password,
        new_password: values.new_password,
      });
      passwordForm.resetFields();
      message.success(t('密码已更新', 'Password updated'));
    } catch (error) {
      message.error(getErrorMessage(error, t('更新密码失败', 'Failed to update password')));
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    Modal.confirm({
      title: t('确认退出登录？', 'Log out?'),
      content: t('退出后需要重新登录才能继续使用。', 'You need to sign in again after logging out.'),
      okText: t('退出登录', 'Log Out'),
      cancelText: t('取消', 'Cancel'),
      onOk: () => {
        storage.clear();
        navigate('/login');
      },
    });
  };

  const handleDeleteAccount = () => {
    Modal.confirm({
      title: t('确认删除账号？', 'Delete account?'),
      content: (
        <div>
          <p className="mb-3">
            {t(
              '该操作会在后端停用账号，并清除本地缓存数据。',
              'This action disables your account on the backend and clears local data.',
            )}
          </p>
          <Alert
            type="warning"
            showIcon
            message={t('该操作较难撤销', 'This action is hard to undo')}
            description={t(
              '你将失去与该账号绑定的资料、联系人和聊天记录。',
              'You will lose profile settings, contacts, and chat history tied to this account.',
            )}
          />
        </div>
      ),
      okText: t('删除账号', 'Delete Account'),
      okType: 'danger',
      cancelText: t('取消', 'Cancel'),
      onOk: async () => {
        try {
          await settingsAPI.deleteAccount();
          storage.clear();
          message.success(t('账号已删除', 'Account deleted'));
          navigate('/login');
        } catch (error) {
          message.error(getErrorMessage(error, t('删除账号失败', 'Failed to delete account')));
        }
      },
    });
  };

  return (
    <div className="agent-shell min-h-screen p-6">
      <div className="mx-auto max-w-6xl">
        <div className="mb-6 flex items-center gap-4">
          <Button icon={<ArrowLeftOutlined />} onClick={onBack} className="btn-secondary">
            {t('返回', 'Back')}
          </Button>
          <div>
            <Title level={3} className="settings-title !mb-0">
              {t('设置', 'Settings')}
            </Title>
            <Text className="text-gray-400">
              {t('管理账号信息、个性偏好和安全控制。', 'Manage account, preferences, and security controls.')}
            </Text>
          </div>
        </div>

        <Row gutter={[24, 24]}>
          <Col xs={24} lg={14}>
            <Card className="card-dark !border-gray-700" variant="borderless" loading={loading}>
              <Title level={4} className="!text-white">
                {t('个人资料', 'Profile')}
              </Title>
              <Text className="mb-5 block text-sm text-gray-400">
                {t(
                  '年龄、性别和职业会参与风险个性化评估，用于调整预警阈值和提示语气。',
                  'Age, gender, and occupation participate in risk personalization for thresholds and prompt tone.',
                )}
              </Text>
              <Form<UserProfileUpdate> form={profileForm} layout="vertical" onFinish={(values) => void handleSaveProfile(values)}>
                <Row gutter={16}>
                  <Col xs={24} md={12}>
                    <Form.Item
                      label={t('用户名', 'Username')}
                      name="username"
                      rules={[
                        { required: true, message: t('请输入用户名', 'Please enter username') },
                        { min: 3, message: t('用户名至少需要 3 个字符', 'Username must be at least 3 characters') },
                      ]}
                    >
                      <Input prefix={<UserOutlined />} className="input-dark" />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item
                      label={t('邮箱', 'Email')}
                      name="email"
                      rules={[
                        { required: true, message: t('请输入邮箱', 'Please enter email') },
                        { type: 'email', message: t('请输入有效的邮箱地址', 'Please enter a valid email address') },
                      ]}
                    >
                      <Input className="input-dark" />
                    </Form.Item>
                  </Col>
                </Row>

                <Row gutter={16}>
                  <Col xs={24} md={12}>
                    <Form.Item
                      label={t('年龄段', 'Age Group')}
                      name="age_group"
                      rules={[{ required: true, message: t('请选择年龄段', 'Please select age group') }]}
                    >
                      <Select className="select-dark" options={ageGroupOptions} />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item
                      label={t('性别', 'Gender')}
                      name="gender"
                      rules={[{ required: true, message: t('请选择性别', 'Please select gender') }]}
                    >
                      <Select className="select-dark" options={genderOptions} />
                    </Form.Item>
                  </Col>
                </Row>

                <Row gutter={16}>
                  <Col xs={24} md={12}>
                    <Form.Item
                      label={t('职业', 'Occupation')}
                      name="occupation"
                      rules={[{ required: true, message: t('请选择职业', 'Please select occupation') }]}
                    >
                      <Select className="select-dark" options={occupationOptions} />
                    </Form.Item>
                  </Col>
                </Row>

                <Form.Item>
                  <Button type="primary" htmlType="submit" className="btn-primary" loading={loading}>
                    {t('保存资料', 'Save Profile')}
                  </Button>
                </Form.Item>
              </Form>
            </Card>

            <Card className="card-dark !mt-6 !border-gray-700" variant="borderless">
              <Title level={4} className="!text-white">
                {t('安全', 'Security')}
              </Title>
              <Form
                form={passwordForm}
                layout="vertical"
                onFinish={(values) => void handleChangePassword(values)}
              >
                <Form.Item
                  label={t('当前密码', 'Current Password')}
                  name="current_password"
                  rules={[{ required: true, message: t('请输入当前密码', 'Please enter current password') }]}
                >
                  <Input.Password prefix={<LockOutlined />} className="input-dark" />
                </Form.Item>
                <Form.Item
                  label={t('新密码', 'New Password')}
                  name="new_password"
                  rules={[
                    { required: true, message: t('请输入新密码', 'Please enter new password') },
                    { min: 6, message: t('密码至少需要 6 个字符', 'Password must be at least 6 characters') },
                  ]}
                >
                  <Input.Password prefix={<LockOutlined />} className="input-dark" />
                </Form.Item>
                <Form.Item
                  label={t('确认新密码', 'Confirm New Password')}
                  name="confirm_password"
                  rules={[{ required: true, message: t('请确认新密码', 'Please confirm new password') }]}
                >
                  <Input.Password prefix={<LockOutlined />} className="input-dark" />
                </Form.Item>
                <Form.Item>
                  <Button type="primary" htmlType="submit" className="btn-primary" loading={loading}>
                    {t('修改密码', 'Change Password')}
                  </Button>
                </Form.Item>
              </Form>

              <Divider className="!border-gray-700" />

              <Space wrap>
                <Button icon={<LogoutOutlined />} onClick={handleLogout}>
                  {t('退出登录', 'Log Out')}
                </Button>
                <Button danger icon={<DeleteOutlined />} onClick={handleDeleteAccount}>
                  {t('删除账号', 'Delete Account')}
                </Button>
              </Space>
            </Card>
          </Col>

          <Col xs={24} lg={10}>
            <Card className="card-dark !border-gray-700" variant="borderless">
              <Title level={4} className="!text-white">
                {t('外观', 'Appearance')}
              </Title>
              <div className="space-y-6">
                <div>
                  <Text className="mb-3 block text-white">{t('主题', 'Theme')}</Text>
                  <Radio.Group
                    value={user?.theme ?? 'dark'}
                    onChange={(event) => void updateSettings({ theme: event.target.value }, t('主题已更新', 'Theme updated'))}
                    className="flex flex-wrap gap-3"
                  >
                    <Radio.Button value="dark">{t('深色', 'Dark')}</Radio.Button>
                    <Radio.Button value="light">{t('浅色', 'Light')}</Radio.Button>
                    <Radio.Button value="system">{t('跟随系统', 'System')}</Radio.Button>
                  </Radio.Group>
                </div>

                <div>
                  <Text className="mb-3 block text-white">{t('语言', 'Language')}</Text>
                  <Radio.Group
                    value={user?.language ?? (isZh ? 'zh-CN' : 'en-US')}
                    onChange={(event) =>
                      void updateSettings({ language: event.target.value }, t('语言已更新', 'Language updated'))
                    }
                    className="flex flex-wrap gap-3"
                  >
                    <Radio.Button value="zh-CN">中文</Radio.Button>
                    <Radio.Button value="en-US">English</Radio.Button>
                  </Radio.Group>
                </div>

                <div>
                  <Text className="mb-3 block text-white">{t('字体大小', 'Font Size')}</Text>
                  <Radio.Group
                    value={user?.font_size ?? 'medium'}
                    onChange={(event) =>
                      void updateSettings({ font_size: event.target.value }, t('字体大小已更新', 'Font size updated'))
                    }
                    className="flex flex-wrap gap-3"
                  >
                    <Radio.Button value="small">{t('小', 'Small')}</Radio.Button>
                    <Radio.Button value="medium">{t('中', 'Medium')}</Radio.Button>
                    <Radio.Button value="large">{t('大', 'Large')}</Radio.Button>
                  </Radio.Group>
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Text className="block text-white">{t('隐私模式', 'Privacy Mode')}</Text>
                    <Text className="text-sm text-gray-400">
                      {t('尽可能在界面中隐藏敏感信息。', 'Hide sensitive information on the interface when possible.')}
                    </Text>
                  </div>
                  <Switch
                    checked={user?.privacy_mode ?? false}
                    onChange={(checked) => void updateSettings({ privacy_mode: checked }, t('隐私模式已更新', 'Privacy mode updated'))}
                  />
                </div>
              </div>
            </Card>

            <Card className="card-dark !mt-6 !border-gray-700" variant="borderless">
              <Title level={4} className="!text-white">
                {t('通知', 'Notifications')}
              </Title>
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <Text className="block text-white">{t('启用通知', 'Enable Notifications')}</Text>
                    <Text className="text-sm text-gray-400">
                      {t('通知推送的总开关。', 'Master switch for notification delivery.')}
                    </Text>
                  </div>
                  <Switch
                    checked={user?.notify_enabled ?? true}
                    onChange={(checked) =>
                      void updateSettings({ notify_enabled: checked }, t('通知设置已更新', 'Notification settings updated'))
                    }
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Text className="block text-white">{t('高风险提醒', 'High-risk Alerts')}</Text>
                    <Text className="text-sm text-gray-400">
                      {t('检测结果为高风险时发送额外提醒。', 'Send extra alerts when risk level is high.')}
                    </Text>
                  </div>
                  <Switch
                    checked={user?.notify_high_risk ?? true}
                    disabled={!user?.notify_enabled}
                    onChange={(checked) =>
                      void updateSettings(
                        { notify_high_risk: checked },
                        t('高风险提醒设置已更新', 'High-risk alert setting updated'),
                      )
                    }
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Text className="block text-white">{t('可信联系人联动', 'Trusted Contact Alerts')}</Text>
                    <Text className="text-sm text-gray-400">
                      {t(
                        '需要升级处理时通知重点联系人流程。',
                        'Notify the key-contact workflow when escalation is needed.',
                      )}
                    </Text>
                  </div>
                  <Switch
                    checked={user?.notify_guardian_alert ?? true}
                    disabled={!user?.notify_enabled}
                    onChange={(checked) =>
                      void updateSettings(
                        { notify_guardian_alert: checked },
                        t('可信联系人联动提醒已更新', 'Trusted contact alert setting updated'),
                      )
                    }
                  />
                </div>
              </div>
            </Card>
          </Col>
        </Row>
      </div>
    </div>
  );
}

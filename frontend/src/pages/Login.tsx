import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { App, Button, Card, Form, Input, Typography } from 'antd';
import { LockOutlined, SafetyOutlined, UserOutlined } from '@ant-design/icons';
import { authAPI } from '../services/api';
import { storage } from '../utils/storage';
import { useI18n } from '../i18n';
import type { LoginRequest } from '../types';

const { Paragraph, Text, Title } = Typography;

type ApiError = {
  response?: {
    data?: {
      detail?: string;
      message?: string;
    };
  };
};

export default function Login() {
  const { message } = App.useApp();
  const { isZh } = useI18n();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const t = (zh: string, en: string) => (isZh ? zh : en);

  const onFinish = async (values: LoginRequest) => {
    setLoading(true);
    try {
      const response = await authAPI.login(values);
      storage.setToken(response.access_token);
      storage.setUser(response.user);
      window.dispatchEvent(new Event('appearance-changed'));
      message.success(t('登录成功', 'Signed in successfully'));
      navigate('/');
    } catch (error) {
      const apiError = error as ApiError;
      const errorMsg =
        apiError.response?.data?.detail ??
        apiError.response?.data?.message ??
        t('登录失败', 'Sign-in failed');
      message.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-darker">
      <div className="hidden lg:flex flex-1 flex-col justify-center items-center p-12 relative overflow-hidden">
        <div className="absolute inset-0 opacity-20">
          <div className="absolute top-20 left-20 h-72 w-72 rounded-full bg-primary blur-3xl" />
          <div className="absolute bottom-24 right-16 h-80 w-80 rounded-full bg-secondary blur-3xl" />
        </div>

        <div className="relative z-10 max-w-lg text-center">
          <SafetyOutlined className="text-7xl text-primary" />
          <Title level={1} className="!mt-8 !mb-4 !text-white">
            {t('反诈预警', 'Anti-fraud Alert')}
          </Title>
          <Paragraph className="!text-lg !text-gray-300">
            {t(
              '在一个界面中分析可疑聊天、图片、音频和视频内容。',
              'Analyze suspicious chats, images, audio, and videos in one place.',
            )}
          </Paragraph>
          <div className="mt-8 space-y-3 text-left">
            <div className="rounded-xl border border-gray-800 bg-dark-lighter p-4 text-gray-300">
              {t('实时诈骗风险评分', 'Real-time fraud risk scoring')}
            </div>
            <div className="rounded-xl border border-gray-800 bg-dark-lighter p-4 text-gray-300">
              {t('紧急联系人联动机制', 'Emergency contact escalation')}
            </div>
            <div className="rounded-xl border border-gray-800 bg-dark-lighter p-4 text-gray-300">
              {t('多模态内容检测', 'Multimodal content detection')}
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-1 items-center justify-center p-6">
        <Card className="w-full max-w-md card-dark !border-gray-700" variant="borderless">
          <div className="mb-8 text-center">
            <div className="mb-4 lg:hidden">
              <SafetyOutlined className="text-5xl text-primary" />
            </div>
            <Title level={2} className="!mb-2 !text-white">
              {t('登录', 'Sign In')}
            </Title>
            <Text className="!text-gray-400">{t('使用你的账号继续。', 'Continue with your account.')}</Text>
          </div>

          <Form<LoginRequest> layout="vertical" size="large" onFinish={onFinish} autoComplete="off">
            <Form.Item
              name="username"
              rules={[
                { required: true, message: t('请输入用户名', 'Please enter your username') },
                { min: 3, message: t('用户名至少需要 3 个字符', 'Username must be at least 3 characters') },
              ]}
            >
              <Input
                prefix={<UserOutlined className="text-gray-400" />}
                placeholder={t('用户名', 'Username')}
                className="input-dark"
              />
            </Form.Item>

            <Form.Item
              name="password"
              rules={[
                { required: true, message: t('请输入密码', 'Please enter your password') },
                { min: 6, message: t('密码至少需要 6 个字符', 'Password must be at least 6 characters') },
              ]}
            >
              <Input.Password
                prefix={<LockOutlined className="text-gray-400" />}
                placeholder={t('密码', 'Password')}
                className="input-dark"
              />
            </Form.Item>

            <Form.Item className="mb-3">
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                className="w-full btn-primary h-12 text-base"
              >
                {t('登录', 'Sign In')}
              </Button>
            </Form.Item>

            <div className="text-center text-sm text-gray-400">
              {t('还没有账号？', 'No account yet?')}
              <Link to="/register" className="ml-1 text-primary hover:text-secondary">
                {t('去注册', 'Register')}
              </Link>
            </div>
          </Form>
        </Card>
      </div>
    </div>
  );
}

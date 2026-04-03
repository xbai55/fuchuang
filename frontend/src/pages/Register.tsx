import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { App, Button, Card, Form, Input, Typography } from 'antd';
import { LockOutlined, MailOutlined, SafetyOutlined, UserOutlined } from '@ant-design/icons';
import { authAPI } from '../services/api';
import { storage } from '../utils/storage';
import { useI18n } from '../i18n';
import type { RegisterRequest } from '../types';

const { Paragraph, Text, Title } = Typography;

interface RegisterFormValues extends RegisterRequest {
  confirmPassword: string;
}

type ApiError = {
  response?: {
    data?: {
      detail?: string;
      message?: string;
    };
  };
};

export default function Register() {
  const { message } = App.useApp();
  const { isZh } = useI18n();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const t = (zh: string, en: string) => (isZh ? zh : en);

  const onFinish = async (values: RegisterFormValues) => {
    if (values.password !== values.confirmPassword) {
      message.error(t('两次输入的密码不一致', 'Passwords do not match'));
      return;
    }

    setLoading(true);
    try {
      const response = await authAPI.register({
        username: values.username,
        email: values.email,
        password: values.password,
      });
      storage.setToken(response.access_token);
      storage.setUser(response.user);
      window.dispatchEvent(new Event('appearance-changed'));
      message.success(t('注册成功', 'Registered successfully'));
      navigate('/');
    } catch (error) {
      const apiError = error as ApiError;
      const errorMsg =
        apiError.response?.data?.detail ?? apiError.response?.data?.message ?? t('注册失败', 'Registration failed');
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
          <SafetyOutlined className="text-7xl text-secondary" />
          <Title level={1} className="!mt-8 !mb-4 !text-white">
            {t('创建账号', 'Create Account')}
          </Title>
          <Paragraph className="!text-lg !text-gray-300">
            {t('一分钟内完成反诈工作台初始化。', 'Set up your anti-fraud workspace in one minute.')}
          </Paragraph>
        </div>
      </div>

      <div className="flex flex-1 items-center justify-center p-6">
        <Card className="w-full max-w-md card-dark !border-gray-700" variant="borderless">
          <div className="mb-8 text-center">
            <div className="mb-4 lg:hidden">
              <SafetyOutlined className="text-5xl text-secondary" />
            </div>
            <Title level={2} className="!mb-2 !text-white">
              {t('注册', 'Register')}
            </Title>
            <Text className="!text-gray-400">{t('创建新账号后即可开始使用。', 'Create a new account to get started.')}</Text>
          </div>

          <Form<RegisterFormValues> layout="vertical" size="large" onFinish={onFinish} autoComplete="off">
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
              name="email"
              rules={[
                { required: true, message: t('请输入邮箱', 'Please enter your email') },
                { type: 'email', message: t('请输入有效的邮箱地址', 'Please enter a valid email') },
              ]}
            >
              <Input
                prefix={<MailOutlined className="text-gray-400" />}
                placeholder={t('邮箱', 'Email')}
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

            <Form.Item
              name="confirmPassword"
              dependencies={['password']}
              rules={[
                { required: true, message: t('请确认密码', 'Please confirm your password') },
                ({ getFieldValue }) => ({
                  validator(_, value) {
                    if (!value || getFieldValue('password') === value) {
                      return Promise.resolve();
                    }
                    return Promise.reject(new Error(t('两次输入的密码不一致', 'Passwords do not match')));
                  },
                }),
              ]}
            >
              <Input.Password
                prefix={<LockOutlined className="text-gray-400" />}
                placeholder={t('确认密码', 'Confirm Password')}
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
                {t('创建账号', 'Create Account')}
              </Button>
            </Form.Item>

            <div className="text-center text-sm text-gray-400">
              {t('已有账号？', 'Already have an account?')}
              <Link to="/login" className="ml-1 text-secondary hover:text-primary">
                {t('去登录', 'Sign In')}
              </Link>
            </div>
          </Form>
        </Card>
      </div>
    </div>
  );
}

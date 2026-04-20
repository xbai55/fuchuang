import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { App, Button, Card, Form, Input, Typography } from 'antd';
import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { authAPI } from '../services/api';
import { useI18n } from '../i18n';
import { storage } from '../utils/storage';
import { APP_NAME, APP_NAME_EN, APP_TAGLINE, APP_TAGLINE_EN, BRAND_LOGO_SRC } from '../utils/brand';
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
  const brandName = t(APP_NAME, APP_NAME_EN);
  const brandTagline = t(APP_TAGLINE, APP_TAGLINE_EN);

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
    <div className="auth-shell flex">
      <div className="auth-brand-panel hidden flex-1 flex-col justify-center px-16 py-12 lg:flex">
        <div className="max-w-xl">
          <div className="brand-logo h-20 w-20 rounded-lg">
            <img src={BRAND_LOGO_SRC} alt={brandName} />
          </div>
          <div className="page-kicker mt-10">Tianshu Mingyu</div>
          <Title level={1} className="!mb-5 !mt-3 !text-6xl !font-semibold !leading-tight !text-white">
            {brandName}
          </Title>
          <Paragraph className="!max-w-md !text-lg !leading-8 !text-gray-300">
            {brandTagline}
          </Paragraph>
          <div className="auth-feature-list mt-12 max-w-md text-left">
            <div className="auth-feature-item py-4">
              {t('实时诈骗风险评分', 'Real-time fraud risk scoring')}
            </div>
            <div className="auth-feature-item py-4">
              {t('可信联系人邮件提醒', 'Trusted contact email alerts')}
            </div>
            <div className="auth-feature-item py-4">
              {t('多模态内容检测', 'Multimodal content detection')}
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-1 items-center justify-center p-6">
        <Card className="auth-card w-full max-w-md" variant="borderless">
          <div className="mb-8 text-center">
            <div className="mb-4 lg:hidden">
              <div className="brand-logo mx-auto h-14 w-14 rounded-lg">
                <img src={BRAND_LOGO_SRC} alt={brandName} />
              </div>
            </div>
            <Title level={2} className="!mb-2 !text-white">
              {t('登录', 'Sign In')}
            </Title>
            <Text className="!text-gray-400">
              {t('继续访问天枢明御。', 'Continue to Tianshu Mingyu.')}
            </Text>
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

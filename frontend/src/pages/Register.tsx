import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Form, Input, Button, App, Card, Typography, Divider, Steps, Alert } from 'antd';
import { UserOutlined, LockOutlined, MailOutlined, SafetyOutlined, CheckCircleOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import { authAPI } from '../services/api';
import { storage } from '../utils/storage';
import type { RegisterRequest } from '../types';

const { Title, Text, Paragraph } = Typography;

export default function Register() {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [formData, setFormData] = useState<Partial<RegisterRequest>>({});

  const steps = [
    { title: '账户信息', icon: <UserOutlined /> },
    { title: '安全设置', icon: <LockOutlined /> },
    { title: '完成注册', icon: <CheckCircleOutlined /> },
  ];

  const onFinishStep1 = (values: any) => {
    setFormData({ ...formData, ...values });
    setCurrentStep(1);
  };

  const onFinishStep2 = async (values: any) => {
    if (values.password !== values.confirmPassword) {
      message.error('两次输入的密码不一致');
      return;
    }

    const data = { ...formData, password: values.password } as RegisterRequest;
    setLoading(true);

    try {
      const response = await authAPI.register(data);
      storage.setToken(response.access_token);
      storage.setUser(response.user);
      message.success('注册成功！欢迎加入');
      setCurrentStep(2);
      setTimeout(() => navigate('/'), 1500);
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || '注册失败，请稍后重试';
      message.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-darker">
      {/* 左侧品牌区域 */}
      <div className="hidden lg:flex flex-1 flex-col justify-center items-center p-12 relative overflow-hidden">
        {/* 背景装饰 */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-20 left-20 w-72 h-72 bg-primary rounded-full filter blur-3xl"></div>
          <div className="absolute bottom-20 right-20 w-96 h-96 bg-secondary rounded-full filter blur-3xl"></div>
        </div>

        <div className="relative z-10 text-center">
          <div className="mb-8">
            <SafetyCertificateOutlined className="text-8xl text-secondary" />
          </div>
          <Title level={1} className="!text-5xl !font-bold !text-white mb-6">
            加入反诈预警
          </Title>
          <Paragraph className="!text-xl text-gray-300 max-w-md">
            创建账户，开启智能防诈保护
          </Paragraph>

          <div className="mt-12 space-y-4">
            <div className="flex items-center gap-3 text-gray-400">
              <CheckCircleOutlined className="text-secondary text-lg" />
              <Text className="!text-gray-300">24/7 全天候智能监控</Text>
            </div>
            <div className="flex items-center gap-3 text-gray-400">
              <CheckCircleOutlined className="text-secondary text-lg" />
              <Text className="!text-gray-300">个性化风险预警</Text>
            </div>
            <div className="flex items-center gap-3 text-gray-400">
              <CheckCircleOutlined className="text-secondary text-lg" />
              <Text className="!text-gray-300">一键联系紧急监护人</Text>
            </div>
          </div>
        </div>
      </div>

      {/* 右侧注册表单 */}
      <div className="flex-1 flex items-center justify-center p-6">
        <Card
          className="w-full max-w-md card-dark !border-gray-700"
          variant="borderless"
        >
          <div className="text-center mb-6">
            <div className="lg:hidden mb-4">
              <SafetyOutlined className="text-5xl text-secondary" />
            </div>
            <Title level={2} className="!text-2xl !font-bold !text-white mb-2">
              创建账号
            </Title>
            <Text className="!text-gray-400">
              填写信息开始保护您的安全
            </Text>
          </div>

          {/* 步骤条 */}
          <Steps
            current={currentStep}
            items={steps}
            className="mb-8 !text-gray-300"
            size="small"
          />

          {currentStep === 0 && (
            <Form
              name="register-step1"
              onFinish={onFinishStep1}
              autoComplete="off"
              size="large"
              layout="vertical"
            >
              <Form.Item
                name="username"
                rules={[
                  { required: true, message: '请输入用户名' },
                  { min: 3, message: '用户名至少3个字符' },
                  { max: 50, message: '用户名最多50个字符' },
                  { pattern: /^[a-zA-Z0-9_]+$/, message: '用户名只能包含字母、数字和下划线' }
                ]}
              >
                <Input
                  prefix={<UserOutlined className="text-gray-400" />}
                  placeholder="用户名"
                  className="input-dark"
                />
              </Form.Item>

              <Form.Item
                name="email"
                rules={[
                  { required: true, message: '请输入邮箱' },
                  { type: 'email', message: '请输入有效的邮箱地址' }
                ]}
              >
                <Input
                  prefix={<MailOutlined className="text-gray-400" />}
                  placeholder="邮箱"
                  className="input-dark"
                />
              </Form.Item>

              <Form.Item className="mb-2">
                <Button
                  type="primary"
                  htmlType="submit"
                  className="w-full btn-primary h-12 text-base"
                >
                  下一步
                </Button>
              </Form.Item>

              <div className="text-center">
                <Text className="!text-gray-400 text-sm">
                  已有账号？
                  <Link to="/login" className="text-secondary hover:text-primary ml-1">
                    立即登录
                  </Link>
                </Text>
              </div>
            </Form>
          )}

          {currentStep === 1 && (
            <Form
              name="register-step2"
              onFinish={onFinishStep2}
              autoComplete="off"
              size="large"
              layout="vertical"
            >
              <Form.Item
                name="password"
                rules={[
                  { required: true, message: '请输入密码' },
                  { min: 6, message: '密码至少6个字符' },
                  { pattern: /^(?=.*[a-zA-Z])(?=.*\d)/, message: '密码需包含字母和数字' }
                ]}
              >
                <Input.Password
                  prefix={<LockOutlined className="text-gray-400" />}
                  placeholder="设置密码（至少6位，包含字母和数字）"
                  className="input-dark"
                />
              </Form.Item>

              <Form.Item
                name="confirmPassword"
                dependencies={['password']}
                rules={[
                  { required: true, message: '请确认密码' },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      if (!value || getFieldValue('password') === value) {
                        return Promise.resolve();
                      }
                      return Promise.reject(new Error('两次输入的密码不一致'));
                    },
                  }),
                ]}
              >
                <Input.Password
                  prefix={<LockOutlined className="text-gray-400" />}
                  placeholder="确认密码"
                  className="input-dark"
                />
              </Form.Item>

              <Form.Item className="mb-4">
                <Button
                  type="primary"
                  htmlType="submit"
                  loading={loading}
                  className="w-full btn-primary h-12 text-base"
                >
                  完成注册
                </Button>
              </Form.Item>

              <Button
                type="link"
                onClick={() => setCurrentStep(0)}
                className="w-full text-gray-400"
              >
                返回上一步
              </Button>
            </Form>
          )}

          {currentStep === 2 && (
            <div className="text-center py-8">
              <CheckCircleOutlined className="text-6xl text-green-500 mb-4" />
              <Title level={3} className="!text-white !mb-2">注册成功！</Title>
              <Text className="!text-gray-400">正在跳转到首页...</Text>
            </div>
          )}

          <Divider className="!border-gray-700">
            <Text className="!text-gray-500 text-xs">安全承诺</Text>
          </Divider>

          <Alert
            message="我们重视您的隐私"
            description="您的个人信息将被加密存储，仅用于反诈预警服务，绝不会分享给第三方"
            type="success"
            showIcon
            className="bg-green-900/20 border-green-800 text-gray-300"
          />
        </Card>
      </div>
    </div>
  );
}

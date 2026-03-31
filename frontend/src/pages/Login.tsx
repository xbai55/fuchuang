import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Form, Input, Button, App, Card, Typography, Divider, Alert } from 'antd';
import { UserOutlined, LockOutlined, SafetyOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { authAPI } from '../services/api';
import { storage } from '../utils/storage';
import type { LoginRequest } from '../types';

const { Title, Text, Paragraph } = Typography;

export default function Login() {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const onFinish = async (values: LoginRequest) => {
    setLoading(true);
    try {
      const response = await authAPI.login(values);
      storage.setToken(response.access_token);
      storage.setUser(response.user);
      message.success('登录成功！欢迎回来');
      navigate('/');
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || '登录失败，请检查用户名和密码';
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
            <SafetyOutlined className="text-8xl text-primary" />
          </div>
          <Title level={1} className="!text-5xl !font-bold !text-white mb-6">
            反诈预警系统
          </Title>
          <Paragraph className="!text-xl text-gray-300 max-w-md">
            AI 智能守护您的财产安全，实时识别诈骗风险
          </Paragraph>

          <div className="mt-12 space-y-4">
            <div className="flex items-center gap-3 text-gray-400">
              <CheckCircleOutlined className="text-primary text-lg" />
              <Text className="!text-gray-300">多模态智能识别（文本/语音/图片/视频）</Text>
            </div>
            <div className="flex items-center gap-3 text-gray-400">
              <CheckCircleOutlined className="text-primary text-lg" />
              <Text className="!text-gray-300">实时风险评估与预警</Text>
            </div>
            <div className="flex items-center gap-3 text-gray-400">
              <CheckCircleOutlined className="text-primary text-lg" />
              <Text className="!text-gray-300">监护人联动保护机制</Text>
            </div>
          </div>
        </div>
      </div>

      {/* 右侧登录表单 */}
      <div className="flex-1 flex items-center justify-center p-6">
        <Card
          className="w-full max-w-md card-dark !border-gray-700"
          variant="borderless"
        >
          <div className="text-center mb-8">
            <div className="lg:hidden mb-4">
              <SafetyOutlined className="text-5xl text-primary" />
            </div>
            <Title level={2} className="!text-2xl !font-bold !text-white mb-2">
              欢迎回来
            </Title>
            <Text className="!text-gray-400">
              登录您的反诈预警账户
            </Text>
          </div>

          <Form
            name="login"
            onFinish={onFinish}
            autoComplete="off"
            size="large"
            layout="vertical"
          >
            <Form.Item
              name="username"
              rules={[
                { required: true, message: '请输入用户名' },
                { min: 3, message: '用户名至少3个字符' }
              ]}
            >
              <Input
                prefix={<UserOutlined className="text-gray-400" />}
                placeholder="用户名"
                className="input-dark"
              />
            </Form.Item>

            <Form.Item
              name="password"
              rules={[
                { required: true, message: '请输入密码' },
                { min: 6, message: '密码至少6个字符' }
              ]}
            >
              <Input.Password
                prefix={<LockOutlined className="text-gray-400" />}
                placeholder="密码"
                className="input-dark"
              />
            </Form.Item>

            <Form.Item className="mb-2">
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                className="w-full btn-primary h-12 text-base"
              >
                登录
              </Button>
            </Form.Item>

            <div className="flex justify-between items-center mb-6">
              <Text className="!text-gray-400 text-sm">
                还没有账号？
                <Link to="/register" className="text-primary hover:text-secondary ml-1">
                  立即注册
                </Link>
              </Text>
            </div>

            <Divider className="!border-gray-700">
              <Text className="!text-gray-500 text-xs">安全提示</Text>
            </Divider>

            <Alert
              message="保护您的账户安全"
              description="请勿在公共设备上保存密码，定期更换密码可有效保护账户安全"
              type="info"
              showIcon
              className="bg-dark-lighter border-gray-700 text-gray-300"
            />
          </Form>
        </Card>
      </div>
    </div>
  );
}

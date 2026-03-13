import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Form, Input, Button, message } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { authAPI } from '../services/api';
import { storage } from '../utils/storage';
import type { LoginRequest } from '../types';

export default function Login() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const onFinish = async (values: LoginRequest) => {
    setLoading(true);
    try {
      const response = await authAPI.login(values);
      storage.setToken(response.access_token);
      storage.setUser(response.user);
      message.success('登录成功！');
      navigate('/');
    } catch (error: any) {
      message.error(error.response?.data?.detail || '登录失败，请检查用户名和密码');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-darker">
      <div className="w-full max-w-md p-8 card-dark">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent mb-2">
            反诈预警系统
          </h1>
          <p className="text-gray-400">AI 智能守护您的财产安全</p>
        </div>

        <Form
          name="login"
          onFinish={onFinish}
          autoComplete="off"
          size="large"
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input
              prefix={<UserOutlined className="text-gray-400" />}
              placeholder="用户名"
              className="input-dark"
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password
              prefix={<LockOutlined className="text-gray-400" />}
              placeholder="密码"
              className="input-dark"
            />
          </Form.Item>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              className="w-full btn-primary"
            >
              登录
            </Button>
          </Form.Item>
        </Form>

        <div className="text-center text-gray-400">
          还没有账号？
          <Link to="/register" className="text-primary hover:text-secondary ml-1">
            立即注册
          </Link>
        </div>
      </div>
    </div>
  );
}

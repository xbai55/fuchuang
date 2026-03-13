import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Form, Input, Button, message } from 'antd';
import { UserOutlined, LockOutlined, MailOutlined } from '@ant-design/icons';
import { authAPI } from '../services/api';
import { storage } from '../utils/storage';
import type { RegisterRequest } from '../types';

export default function Register() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const onFinish = async (values: RegisterRequest) => {
    setLoading(true);
    try {
      const response = await authAPI.register(values);
      storage.setToken(response.access_token);
      storage.setUser(response.user);
      message.success('注册成功！');
      navigate('/');
    } catch (error: any) {
      message.error(error.response?.data?.detail || '注册失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-darker">
      <div className="w-full max-w-md p-8 card-dark">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent mb-2">
            创建账号
          </h1>
          <p className="text-gray-400">加入反诈预警系统</p>
        </div>

        <Form
          name="register"
          onFinish={onFinish}
          autoComplete="off"
          size="large"
        >
          <Form.Item
            name="username"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, message: '用户名至少3个字符' },
              { max: 50, message: '用户名最多50个字符' }
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

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              className="w-full btn-primary"
            >
              注册
            </Button>
          </Form.Item>
        </Form>

        <div className="text-center text-gray-400">
          已有账号？
          <Link to="/login" className="text-primary hover:text-secondary ml-1">
            立即登录
          </Link>
        </div>
      </div>
    </div>
  );
}

import axios from 'axios';
import type {
  AuthResponse,
  User,
  LoginRequest,
  RegisterRequest,
  Contact,
  ContactCreate,
  FraudDetectionRequest,
  FraudDetectionResponse,
  ChatHistory
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// 创建 axios 实例
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：添加 token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器：处理错误
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token 过期，清除本地存储并跳转到登录页
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ========== 认证 API ==========
export const authAPI = {
  // 登录
  login: async (data: LoginRequest): Promise<AuthResponse> => {
    const formData = new FormData();
    formData.append('username', data.username);
    formData.append('password', data.password);
    
    const response = await api.post<AuthResponse>('/api/auth/login', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // 注册
  register: async (data: RegisterRequest): Promise<AuthResponse> => {
    const response = await api.post<AuthResponse>('/api/auth/register', data);
    return response.data;
  },

  // 获取当前用户信息
  getCurrentUser: async (): Promise<User> => {
    const response = await api.get<User>('/api/auth/me');
    return response.data;
  },

  // 更新用户信息
  updateUser: async (user_role?: string, guardian_name?: string): Promise<User> => {
    const response = await api.put<User>('/api/auth/me', { user_role, guardian_name });
    return response.data;
  },
};

// ========== 联系人 API ==========
export const contactsAPI = {
  // 获取联系人列表
  getContacts: async (): Promise<Contact[]> => {
    const response = await api.get<Contact[]>('/api/contacts/');
    return response.data;
  },

  // 创建联系人
  createContact: async (data: ContactCreate): Promise<Contact> => {
    const response = await api.post<Contact>('/api/contacts/', data);
    return response.data;
  },

  // 更新联系人
  updateContact: async (id: number, data: Partial<ContactCreate>): Promise<Contact> => {
    const response = await api.put<Contact>(`/api/contacts/${id}`, data);
    return response.data;
  },

  // 删除联系人
  deleteContact: async (id: number): Promise<void> => {
    await api.delete(`/api/contacts/${id}`);
  },
};

// ========== 反诈检测 API ==========
export const fraudAPI = {
  // 检测诈骗
  detect: async (data: FraudDetectionRequest): Promise<FraudDetectionResponse> => {
    const response = await api.post<FraudDetectionResponse>('/api/fraud/detect', data);
    return response.data;
  },

  // 获取聊天历史
  getHistory: async (): Promise<ChatHistory[]> => {
    const response = await api.get<ChatHistory[]>('/api/fraud/history');
    return response.data;
  },
};

export default api;

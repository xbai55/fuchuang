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
  FraudAsyncResponse,
  FraudTask,
  ChatHistory,
  AgentChatRequest,
  AgentChatResponse,
  AgentChatAsyncResponse,
  AgentTask,
  UserSettings,
  UserProfileUpdate,
  ChangePasswordRequest
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_BASE_URL = API_BASE_URL.replace(/\/$/, '').replace(/^http/i, 'ws');

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

    const response = await api.post<{ code: number; message: string; data: AuthResponse }>('/api/auth/login', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data.data;
  },

  // 注册
  register: async (data: RegisterRequest): Promise<AuthResponse> => {
    const response = await api.post<{ code: number; message: string; data: AuthResponse }>('/api/auth/register', data);
    return response.data.data;
  },

  // 获取当前用户信息
  getCurrentUser: async (): Promise<User> => {
    const response = await api.get<{ code: number; message: string; data: User }>('/api/auth/me');
    return response.data.data;
  },

  // 更新用户信息
  updateUser: async (user_role?: string, guardian_name?: string): Promise<User> => {
    const response = await api.put<{ code: number; message: string; data: User }>('/api/auth/me', { user_role, guardian_name });
    return response.data.data;
  },
};

// ========== 用户设置 API ==========
export const settingsAPI = {
  // 获取用户设置
  getSettings: async (): Promise<User> => {
    const response = await api.get<{ code: number; message: string; data: User }>('/api/settings/');
    return response.data.data;
  },

  // 更新用户设置（部分更新）
  updateSettings: async (settings: UserSettings): Promise<User> => {
    const response = await api.patch<{ code: number; message: string; data: User }>('/api/settings/', settings);
    return response.data.data;
  },

  // 更新用户资料
  updateProfile: async (profile: UserProfileUpdate): Promise<User> => {
    const response = await api.put<{ code: number; message: string; data: User }>('/api/settings/profile', profile);
    return response.data.data;
  },

  // 修改密码
  changePassword: async (data: ChangePasswordRequest): Promise<void> => {
    await api.post('/api/settings/change-password', data);
  },

  // 注销账号
  deleteAccount: async (): Promise<void> => {
    await api.delete('/api/settings/account');
  },
};

// ========== 联系人 API ==========
export const contactsAPI = {
  // 获取联系人列表
  getContacts: async (): Promise<Contact[]> => {
    const response = await api.get<{ code: number; message: string; data: Contact[] }>('/api/contacts/');
    return response.data.data;
  },

  // 创建联系人
  createContact: async (data: ContactCreate): Promise<Contact> => {
    const response = await api.post<{ code: number; message: string; data: Contact }>('/api/contacts/', data);
    return response.data.data;
  },

  // 更新联系人
  updateContact: async (id: number, data: Partial<ContactCreate>): Promise<Contact> => {
    const response = await api.put<{ code: number; message: string; data: Contact }>(`/api/contacts/${id}`, data);
    return response.data.data;
  },

  // 删除联系人
  deleteContact: async (id: number): Promise<void> => {
    await api.delete(`/api/contacts/${id}`);
  },
};

// ========== 反诈检测 API ==========
export const fraudAPI = {
  // 检测诈骗 - 支持多模态文件上传
  detect: async (data: FraudDetectionRequest): Promise<FraudDetectionResponse> => {
    const formData = new FormData();
    formData.append('message', data.message);

    if (data.audio_file) {
      formData.append('audio_file', data.audio_file);
    }
    if (data.image_file) {
      formData.append('image_file', data.image_file);
    }
    if (data.video_file) {
      formData.append('video_file', data.video_file);
    }

    const response = await api.post<{ code: number; message: string; data: FraudDetectionResponse }>('/api/fraud/detect', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data.data;
  },

  // 异步检测诈骗 - 返回 task_id
  detectAsync: async (data: FraudDetectionRequest): Promise<FraudAsyncResponse> => {
    const formData = new FormData();
    formData.append('message', data.message);

    if (data.audio_file) {
      formData.append('audio_file', data.audio_file);
    }
    if (data.image_file) {
      formData.append('image_file', data.image_file);
    }
    if (data.video_file) {
      formData.append('video_file', data.video_file);
    }

    const response = await api.post<{ code: number; message: string; data: FraudAsyncResponse }>('/api/fraud/detect-async', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data.data;
  },

  // 查询任务状态（WebSocket 断开时可作为降级轮询）
  getTaskStatus: async (taskId: string): Promise<FraudTask> => {
    const response = await api.get<{ code: number; message: string; data: FraudTask }>(`/api/fraud/tasks/${taskId}`);
    return response.data.data;
  },

  // 创建任务实时推送连接
  createTaskSocket: (taskId: string): WebSocket => {
    const token = localStorage.getItem('access_token') || '';
    const wsUrl = `${WS_BASE_URL}/api/fraud/ws/tasks/${taskId}?token=${encodeURIComponent(token)}`;
    return new WebSocket(wsUrl);
  },

  // 获取聊天历史
  getHistory: async (): Promise<ChatHistory[]> => {
    const response = await api.get<{ code: number; message: string; data: { items: ChatHistory[] } }>('/api/fraud/history');
    return response.data.data.items;
  },

  // 删除单条聊天历史
  deleteHistory: async (historyId: number): Promise<void> => {
    await api.delete(`/api/fraud/history/${historyId}`);
  },

  // 清空聊天历史
  clearHistory: async (): Promise<number> => {
    const response = await api.delete<{ code: number; message: string; data: { deleted: number } }>('/api/fraud/history');
    return response.data.data.deleted;
  },
};

// ========== Agent 聊天 API ==========
export const agentAPI = {
  chat: async (data: AgentChatRequest): Promise<AgentChatResponse> => {
    const response = await api.post<{ code: number; message: string; data: AgentChatResponse }>('/api/agent/chat', data);
    return response.data.data;
  },

  // Agent 异步聊天 - 返回 task_id
  chatAsync: async (data: AgentChatRequest): Promise<AgentChatAsyncResponse> => {
    const response = await api.post<{ code: number; message: string; data: AgentChatAsyncResponse }>('/api/agent/chat-async', data);
    return response.data.data;
  },

  // 查询 Agent 异步任务状态
  getTaskStatus: async (taskId: string): Promise<AgentTask> => {
    const response = await api.get<{ code: number; message: string; data: AgentTask }>(`/api/agent/tasks/${taskId}`);
    return response.data.data;
  },

  // 创建 Agent 任务实时推送连接
  createTaskSocket: (taskId: string): WebSocket => {
    const token = localStorage.getItem('access_token') || '';
    const wsUrl = `${WS_BASE_URL}/api/agent/ws/tasks/${taskId}?token=${encodeURIComponent(token)}`;
    return new WebSocket(wsUrl);
  },
};

export default api;

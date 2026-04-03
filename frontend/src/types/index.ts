// 用户相关类型
export interface User {
  id: number;
  username: string;
  email: string;
  user_role: 'elderly' | 'student' | 'finance' | 'general';
  guardian_name: string;
  // 设置字段
  theme: 'dark' | 'light' | 'system';
  notify_enabled: boolean;
  notify_high_risk: boolean;
  notify_guardian_alert: boolean;
  language: 'zh-CN' | 'en-US';
  font_size: 'small' | 'medium' | 'large';
  privacy_mode: boolean;
}

// 用户设置更新类型
export interface UserSettings {
  theme?: 'dark' | 'light' | 'system';
  notify_enabled?: boolean;
  notify_high_risk?: boolean;
  notify_guardian_alert?: boolean;
  language?: 'zh-CN' | 'en-US';
  font_size?: 'small' | 'medium' | 'large';
  privacy_mode?: boolean;
}

// 用户资料更新类型
export interface UserProfileUpdate {
  username?: string;
  email?: string;
  user_role?: 'elderly' | 'student' | 'finance' | 'general';
  guardian_name?: string;
}

// 修改密码请求类型
export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
  confirm_password?: string; // 前端校验用，不传后端
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

// 联系人相关类型
export interface Contact {
  id: number;
  user_id: number;
  name: string;
  phone: string;
  relationship: string;
  is_guardian: boolean;
  created_at: string;
}

export interface ContactCreate {
  name: string;
  phone: string;
  relationship: string;
  is_guardian: boolean;
}

// 反诈检测相关类型
export interface FraudDetectionRequest {
  message: string;
  audio_file?: File | null;
  image_file?: File | null;
  video_file?: File | null;
}

export interface FraudDetectionResponse {
  risk_score: number;
  risk_level: 'low' | 'medium' | 'high';
  scam_type: string;
  warning_message: string;
  final_report: string;
  guardian_alert: boolean;
}

export interface FraudEarlyWarning {
  risk_score: number;
  risk_level: 'low' | 'medium' | 'high';
  warning_message: string;
  risk_clues?: string[];
  source?: string;
  is_preliminary?: boolean;
}

export type FraudTaskStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'timeout';

export interface FraudTask {
  task_id: string;
  status: FraudTaskStatus;
  progress: number;
  result?: FraudDetectionResponse | null;
  error?: string | null;
  created_at: number;
  started_at?: number | null;
  completed_at?: number | null;
  elapsed_time: number;
  input_summary: string;
}

export interface FraudAsyncResponse {
  task_id: string;
  status: FraudTaskStatus;
  estimated_time: number;
  poll_url: string;
  ws_url: string;
  early_warning?: FraudEarlyWarning | null;
}

export interface FraudTaskWsMessage {
  event:
    | 'connected'
    | 'task_update'
    | 'task_completed'
    | 'task_failed'
    | 'error'
    | 'report_stream_started'
    | 'report_chunk'
    | 'report_stream_finished';
  task_id: string;
  task?: FraudTask;
  result?: FraudDetectionResponse;
  error?: string;
  message?: string;
  seq?: number;
  timestamp?: number;
  chunk?: string;
  chunk_index?: number;
  total_chunks?: number;
  done?: boolean;
}

export interface AgentChatRequest {
  message: string;
  conversation_id?: string;
  context?: Record<string, unknown>;
}

export interface AgentChatResponse {
  message: string;
  suggestions: string[];
  tool_calls: Array<Record<string, unknown>>;
  conversation_id: string;
}

export type AgentTaskStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'timeout';

export interface AgentTask {
  task_id: string;
  status: AgentTaskStatus;
  progress: number;
  result?: AgentChatResponse | null;
  error?: string | null;
  created_at: number;
  started_at?: number | null;
  completed_at?: number | null;
  elapsed_time: number;
  input_summary: string;
}

export interface AgentChatAsyncResponse {
  task_id: string;
  status: AgentTaskStatus;
  estimated_time: number;
  poll_url: string;
  ws_url: string;
}

export interface AgentTaskWsMessage {
  event:
    | 'connected'
    | 'task_update'
    | 'task_completed'
    | 'task_failed'
    | 'error'
    | 'agent_stream_started'
    | 'agent_chunk'
    | 'agent_stream_finished';
  task_id: string;
  task?: AgentTask;
  result?: AgentChatResponse;
  error?: string;
  message?: string;
  seq?: number;
  timestamp?: number;
  chunk?: string;
  chunk_index?: number;
  total_chunks?: number;
}

// 聊天历史类型
export interface ChatHistory {
  id: number;
  user_message: string;
  bot_response: string;
  risk_score: number;
  risk_level: string;
  scam_type: string;
  chat_mode?: 'fraud' | 'agent';
  guardian_alert: boolean;
  created_at: string;
}

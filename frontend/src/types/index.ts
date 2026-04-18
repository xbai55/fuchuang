// 用户相关类型
export type RiskLevel = 'low' | 'medium' | 'high';

export type UserRole =
  | 'general'
  | 'elderly'
  | 'child'
  | 'young_adult'
  | 'student'
  | 'enterprise_staff'
  | 'self_employed'
  | 'retired_group'
  | 'public_officer'
  | 'finance_practitioner'
  | 'other';

export type AgeGroup = 'unknown' | 'child' | 'young_adult' | 'elderly';
export type Gender = 'unknown' | 'male' | 'female';
export type Occupation =
  | 'student'
  | 'enterprise_staff'
  | 'self_employed'
  | 'retired_group'
  | 'public_officer'
  | 'finance_practitioner'
  | 'other';

export interface User {
  id: number;
  username: string;
  email: string;
  user_role: UserRole;
  age_group: AgeGroup;
  gender: Gender;
  occupation: Occupation;
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
  user_role?: UserRole;
  age_group?: AgeGroup;
  gender?: Gender;
  occupation?: Occupation;
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
  client_request_started_at_ms?: number;
}

export interface FraudDetectionResponse {
  risk_score: number;
  llm_risk_score?: number | null;
  llm_risk_score_available?: boolean;
  risk_level: RiskLevel;
  scam_type: string;
  warning_message: string;
  final_report: string;
  guardian_alert: boolean;
  performance_timing?: Record<string, unknown>;
}

export interface FraudAlertPayload {
  title: string;
  riskScore: number;
  riskLevel: RiskLevel;
  scamType: string;
  summary: string;
  warningMessage: string;
  evidence: string[];
  recommendations: string[];
  guardianAlert: boolean;
  finalReport?: string;
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
  performance_timing?: Record<string, unknown>;
}

export interface FraudTaskWsMessage {
  event:
    | 'connected'
    | 'task_update'
    | 'task_completed'
    | 'task_failed'
    | 'error'
    | 'report_stream_started'
    | 'llm_risk_update'
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
  risk_score?: number;
  risk_level?: 'low' | 'medium' | 'high';
  scam_type?: string;
  warning_message?: string;
  guardian_alert?: boolean;
  is_preliminary?: boolean;
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

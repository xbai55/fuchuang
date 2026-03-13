// 用户相关类型
export interface User {
  id: number;
  username: string;
  email: string;
  user_role: 'elderly' | 'student' | 'finance' | 'general';
  guardian_name: string;
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
  audio_url?: string;
  image_url?: string;
}

export interface FraudDetectionResponse {
  risk_score: number;
  risk_level: 'low' | 'medium' | 'high';
  scam_type: string;
  warning_message: string;
  final_report: string;
  guardian_alert: boolean;
}

// 聊天历史类型
export interface ChatHistory {
  id: number;
  user_message: string;
  bot_response: string;
  risk_score: number;
  risk_level: string;
  scam_type: string;
  guardian_alert: boolean;
  created_at: string;
}

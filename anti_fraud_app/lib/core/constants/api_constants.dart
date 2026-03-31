/// API 常量配置
class ApiConstants {
  ApiConstants._();

  // 开发环境
  static const String devBaseUrl = 'http://10.0.2.2:8000';  // Android 模拟器访问主机
  // static const String devBaseUrl = 'http://localhost:8000';  // iOS 模拟器

  // 生产环境
  static const String prodBaseUrl = 'https://your-domain.com';

  // 是否为开发模式
  static const bool isDev = true;

  // 基础 URL
  static String get baseUrl => isDev ? devBaseUrl : prodBaseUrl;

  // API 版本前缀
  static const String apiPrefix = '/api';

  // 完整基础 URL
  static String get fullBaseUrl => '$baseUrl$apiPrefix';

  // 超时配置（秒）
  static const int connectTimeout = 30;
  static const int receiveTimeout = 30;
  static const int sendTimeout = 30;

  // API 端点
  static const String login = '/auth/login';
  static const String register = '/auth/register';
  static const String refreshToken = '/auth/refresh';
  static const String logout = '/auth/logout';
  static const String me = '/auth/me';

  static const String contacts = '/contacts/';
  static const String fraudDetect = '/fraud/detect';
  static const String fraudDetectAsync = '/fraud/detect-async';
  static const String taskStatus = '/fraud/tasks/';
  static const String history = '/fraud/history';
  static const String agentChat = '/agent/chat';
}

/// API 常量配置
class ApiConstants {
  ApiConstants._();

  static const String appName = '天枢明御';

  // 真机调试默认访问电脑 WLAN 地址；可通过 --dart-define=API_BASE_URL=... 覆盖。
  static const String configuredBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://192.168.1.101:8000',
  );

  // 生产环境
  static const String prodBaseUrl = String.fromEnvironment(
    'API_PROD_BASE_URL',
    defaultValue: 'https://your-domain.com',
  );

  // 是否为开发模式
  static const bool isDev = bool.fromEnvironment('APP_DEV', defaultValue: true);

  // 基础 URL
  static String get baseUrl => isDev ? configuredBaseUrl : prodBaseUrl;

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
  static const String settings = '/settings/';
  static const String settingsProfile = '/settings/profile';
  static const String settingsChangePassword = '/settings/change-password';
  static const String settingsAccount = '/settings/account';
  static const String fraudDetect = '/fraud/detect';
  static const String fraudDetectAsync = '/fraud/detect-async';
  static const String taskStatus = '/fraud/tasks/';
  static const String history = '/fraud/history';
  static const String agentChat = '/agent/chat';

  static const String mobileDefaultPassword = String.fromEnvironment(
    'MOBILE_DEFAULT_PASSWORD',
    defaultValue: 'mobile123456',
  );
}

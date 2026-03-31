/// API 异常基类
class ApiException implements Exception {
  final String message;
  final int? code;
  final dynamic data;

  ApiException({
    required this.message,
    this.code,
    this.data,
  });

  @override
  String toString() => 'ApiException: $message (code: $code)';
}

/// 网络异常
class NetworkException extends ApiException {
  NetworkException({String message = '网络连接失败'}) : super(message: message, code: -1);
}

/// 服务器异常
class ServerException extends ApiException {
  ServerException({String message = '服务器错误', int code = 500}) : super(message: message, code: code);
}

/// 认证异常
class AuthException extends ApiException {
  AuthException({String message = '认证失败', int code = 401}) : super(message: message, code: code);
}

/// Token 过期异常
class TokenExpiredException extends AuthException {
  TokenExpiredException() : super(message: '登录已过期，请重新登录', code: 4001);
}

/// 请求参数异常
class BadRequestException extends ApiException {
  BadRequestException({String message = '请求参数错误', int code = 400}) : super(message: message, code: code);
}

/// 业务异常
class BusinessException extends ApiException {
  BusinessException({required String message, required int code}) : super(message: message, code: code);
}

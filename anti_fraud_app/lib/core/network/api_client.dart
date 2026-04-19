import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import '../constants/api_constants.dart';
import '../storage/local_storage.dart';
import 'api_exception.dart';

/// API 客户端
/// 封装 Dio，提供统一的 HTTP 请求接口
class ApiClient {
  static final ApiClient _instance = ApiClient._internal();
  factory ApiClient() => _instance;
  ApiClient._internal();

  late Dio _dio;
  final LocalStorage _storage = LocalStorage();
  bool _isRefreshing = false;
  final List<void Function()> _refreshSubscribers = [];

  /// 初始化 Dio
  void init() {
    _dio = Dio(BaseOptions(
      baseUrl: ApiConstants.fullBaseUrl,
      connectTimeout: const Duration(seconds: ApiConstants.connectTimeout),
      receiveTimeout: const Duration(seconds: ApiConstants.receiveTimeout),
      sendTimeout: const Duration(seconds: ApiConstants.sendTimeout),
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    ));

    _setupInterceptors();
  }

  /// 设置拦截器
  void _setupInterceptors() {
    // 请求拦截器
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        // 添加 Token
        final token = _storage.getAccessToken();
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }

        if (kDebugMode) {
          debugPrint('🌐 [${options.method}] ${options.path}');
          debugPrint('Headers: ${options.headers}');
          if (options.data != null) {
            debugPrint('Data: ${options.data}');
          }
        }

        return handler.next(options);
      },
      onResponse: (response, handler) {
        if (kDebugMode) {
          debugPrint(
              '✅ [${response.statusCode}] ${response.requestOptions.path}');
          debugPrint('Response: ${response.data}');
        }
        return handler.next(response);
      },
      onError: (error, handler) async {
        if (kDebugMode) {
          debugPrint(
              '❌ [${error.response?.statusCode}] ${error.requestOptions.path}');
          debugPrint('Error: ${error.message}');
        }

        // 处理 Token 过期
        if (error.response?.statusCode == 401) {
          final errorData = error.response?.data;
          final hasRefreshToken = _storage.getRefreshToken() != null;
          if (hasRefreshToken ||
              (errorData != null && errorData['code'] == 4001)) {
            // Token 过期，尝试刷新
            final refreshed = await _refreshToken();
            if (refreshed) {
              // 重试原请求
              final retryResponse = await _retry(error.requestOptions);
              return handler.resolve(retryResponse);
            } else {
              // 刷新失败，清除登录状态
              await _storage.clearAll();
              return handler.reject(error);
            }
          }
        }

        return handler.next(error);
      },
    ));

    // 日志拦截器（仅调试模式）
    if (kDebugMode) {
      _dio.interceptors.add(LogInterceptor(
        requestBody: true,
        responseBody: true,
      ));
    }
  }

  /// 确保移动端有可用登录态。当前 App 暂无登录页，开发环境下创建/复用本机游客账号。
  Future<void> ensureAuthenticated() async {
    if (_storage.getAccessToken() != null) {
      return;
    }

    if (_storage.getRefreshToken() != null && await _refreshToken()) {
      return;
    }

    final username = _storage.getMobileUsername() ??
        'mobile_${DateTime.now().millisecondsSinceEpoch}';
    const password = ApiConstants.mobileDefaultPassword;

    try {
      await loginWithPassword(username: username, password: password);
      await _storage.setMobileUsername(username);
      return;
    } on ApiException {
      // 账号不存在或密码不匹配时继续尝试注册一个本机游客账号。
    }

    final createdUsername = 'mobile_${DateTime.now().millisecondsSinceEpoch}';
    await registerAccount(
      username: createdUsername,
      email: '$createdUsername@tianshumingyu.com',
      password: password,
    );
    await _storage.setMobileUsername(createdUsername);
  }

  Future<Map<String, dynamic>> loginWithPassword({
    required String username,
    required String password,
  }) async {
    final formData = FormData.fromMap({
      'username': username,
      'password': password,
    });

    final response = await _dio.post(
      ApiConstants.login,
      data: formData,
      options: Options(
        headers: {'Content-Type': 'multipart/form-data'},
        validateStatus: _acceptBackendBusinessStatus,
      ),
    );

    final data = _parseResponse(response) as Map<String, dynamic>;
    await saveAuthData(data);
    return data;
  }

  Future<Map<String, dynamic>> registerAccount({
    required String username,
    required String email,
    required String password,
  }) async {
    final response = await _dio.post(
      ApiConstants.register,
      data: {
        'username': username,
        'email': email,
        'password': password,
      },
      options: Options(validateStatus: _acceptBackendBusinessStatus),
    );

    final data = _parseResponse(response) as Map<String, dynamic>;
    await saveAuthData(data);
    return data;
  }

  Future<void> saveAuthData(Map<String, dynamic> data) async {
    final accessToken = data['access_token'] as String?;
    final refreshToken = data['refresh_token'] as String?;

    if (accessToken == null || refreshToken == null) {
      throw ApiException(message: '登录响应缺少 Token', code: -1);
    }

    await _storage.setAccessToken(accessToken);
    await _storage.setRefreshToken(refreshToken);

    final user = data['user'];
    if (user is Map<String, dynamic>) {
      await _storage.setUserInfo(user);
    }
  }

  Future<void> clearSession() async {
    try {
      if (_storage.getAccessToken() != null) {
        await _dio.post(ApiConstants.logout);
      }
    } catch (_) {
      // 本地退出优先，服务端登出失败不阻断用户离开当前会话。
    } finally {
      await _storage.clearAll();
    }
  }

  /// 刷新 Token
  Future<bool> _refreshToken() async {
    if (_isRefreshing) {
      // 等待刷新完成
      final completer = Completer<bool>();
      _refreshSubscribers.add(() => completer.complete(true));
      return completer.future;
    }

    _isRefreshing = true;

    try {
      final refreshToken = _storage.getRefreshToken();
      if (refreshToken == null) {
        return false;
      }

      final response = await _dio.post(ApiConstants.refreshToken, data: {
        'refresh_token': refreshToken,
      });

      if (response.statusCode == 200) {
        final data = response.data['data'];
        await _storage.setAccessToken(data['access_token']);
        await _storage.setRefreshToken(data['refresh_token']);

        // 通知等待的请求
        for (var callback in _refreshSubscribers) {
          callback();
        }
        _refreshSubscribers.clear();

        return true;
      }
    } catch (e) {
      debugPrint('Refresh token failed: $e');
    } finally {
      _isRefreshing = false;
    }

    return false;
  }

  /// 重试请求
  Future<Response> _retry(RequestOptions requestOptions) async {
    final token = _storage.getAccessToken();
    final options = Options(
      method: requestOptions.method,
      headers: {
        ...requestOptions.headers,
        'Authorization': 'Bearer $token',
      },
    );

    return _dio.request(
      requestOptions.path,
      data: requestOptions.data,
      queryParameters: requestOptions.queryParameters,
      options: options,
    );
  }

  /// 解析响应
  dynamic _parseResponse(Response response) {
    if (response.data == null) {
      throw ServerException(message: '空响应');
    }

    final responseData = response.data as Map<String, dynamic>;
    final code = responseData['code'] as int;
    final message = responseData['message'] as String;

    if (code == 200) {
      return responseData['data'];
    }

    // 业务错误
    switch (code) {
      case 400:
        throw BadRequestException(message: message, code: code);
      case 4001:
        throw TokenExpiredException();
      case 401:
        throw AuthException(message: message, code: code);
      case 403:
        throw AuthException(message: message, code: code);
      case 404:
        throw BadRequestException(message: message, code: code);
      case 429:
        throw BusinessException(message: '请求过于频繁，请稍后再试', code: code);
      case 500:
      case 503:
        throw ServerException(message: message, code: code);
      default:
        throw BusinessException(message: message, code: code);
    }
  }

  bool _acceptBackendBusinessStatus(int? status) {
    return status != null && status < 500;
  }

  /// GET 请求
  Future<T?> get<T>(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    try {
      final response = await _dio.get(
        path,
        queryParameters: queryParameters,
        options: options,
      );
      return _parseResponse(response);
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  /// POST 请求
  Future<T?> post<T>(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    try {
      final response = await _dio.post(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
      );
      return _parseResponse(response);
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  /// POST 表单数据（用于文件上传）
  Future<T?> postForm<T>(
    String path, {
    required FormData formData,
    Map<String, dynamic>? queryParameters,
    ProgressCallback? onSendProgress,
  }) async {
    try {
      final response = await _dio.post(
        path,
        data: formData,
        queryParameters: queryParameters,
        options: Options(
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        ),
        onSendProgress: onSendProgress,
      );
      return _parseResponse(response);
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  /// PUT 请求
  Future<T?> put<T>(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
  }) async {
    try {
      final response = await _dio.put(
        path,
        data: data,
        queryParameters: queryParameters,
      );
      return _parseResponse(response);
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  /// PATCH 请求
  Future<T?> patch<T>(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
  }) async {
    try {
      final response = await _dio.patch(
        path,
        data: data,
        queryParameters: queryParameters,
      );
      return _parseResponse(response);
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  /// DELETE 请求
  Future<T?> delete<T>(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
  }) async {
    try {
      final response = await _dio.delete(
        path,
        data: data,
        queryParameters: queryParameters,
      );
      return _parseResponse(response);
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  /// 处理 Dio 错误
  Exception _handleDioError(DioException error) {
    switch (error.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return NetworkException(message: '连接超时，请检查网络');
      case DioExceptionType.connectionError:
        return NetworkException(message: '网络连接失败，请检查网络设置');
      case DioExceptionType.badResponse:
        final statusCode = error.response?.statusCode;
        final message = error.response?.data?['message'] ?? '服务器错误';
        return ServerException(message: message, code: statusCode ?? 500);
      case DioExceptionType.cancel:
        return ApiException(message: '请求已取消', code: -1);
      default:
        return ApiException(message: '网络错误：${error.message}', code: -1);
    }
  }

  /// 轮询任务状态
  Stream<TaskStatusResponse> pollTaskStatus(
    String taskId, {
    Duration interval = const Duration(seconds: 2),
    Duration timeout = const Duration(minutes: 5),
  }) async* {
    final startTime = DateTime.now();

    while (true) {
      // 检查超时
      if (DateTime.now().difference(startTime) > timeout) {
        throw ApiException(message: '任务轮询超时', code: -1);
      }

      try {
        final response = await get<Map<String, dynamic>>(
          '${ApiConstants.taskStatus}$taskId',
        );

        if (response != null) {
          final taskStatus = TaskStatusResponse.fromJson(response);
          yield taskStatus;

          // 任务完成或失败，停止轮询
          if (taskStatus.isCompleted || taskStatus.isFailed) {
            break;
          }
        }
      } catch (e) {
        debugPrint('Poll task status error: $e');
      }

      // 等待后再次轮询
      await Future.delayed(interval);
    }
  }
}

/// 任务状态响应
class TaskStatusResponse {
  final String taskId;
  final String status;
  final int progress;
  final Map<String, dynamic>? result;
  final String? error;
  final double elapsedTime;
  final String? inputSummary;

  TaskStatusResponse({
    required this.taskId,
    required this.status,
    required this.progress,
    this.result,
    this.error,
    required this.elapsedTime,
    this.inputSummary,
  });

  bool get isCompleted => status == 'completed';
  bool get isFailed => status == 'failed';
  bool get isProcessing => status == 'processing';
  bool get isPending => status == 'pending';

  factory TaskStatusResponse.fromJson(Map<String, dynamic> json) {
    return TaskStatusResponse(
      taskId: json['task_id'] as String,
      status: json['status'] as String,
      progress: json['progress'] as int,
      result: json['result'] as Map<String, dynamic>?,
      error: json['error'] as String?,
      elapsedTime: (json['elapsed_time'] as num).toDouble(),
      inputSummary: json['input_summary'] as String?,
    );
  }
}

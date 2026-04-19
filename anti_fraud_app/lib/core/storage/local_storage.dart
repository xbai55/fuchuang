import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';

/// 本地存储管理器
class LocalStorage {
  static final LocalStorage _instance = LocalStorage._internal();
  factory LocalStorage() => _instance;
  LocalStorage._internal();

  SharedPreferences? _prefs;

  Future<void> init() async {
    _prefs = await SharedPreferences.getInstance();
  }

  // Token 管理
  Future<void> setAccessToken(String token) async {
    await _prefs?.setString('access_token', token);
  }

  String? getAccessToken() {
    return _prefs?.getString('access_token');
  }

  Future<void> setRefreshToken(String token) async {
    await _prefs?.setString('refresh_token', token);
  }

  String? getRefreshToken() {
    return _prefs?.getString('refresh_token');
  }

  Future<void> clearTokens() async {
    await _prefs?.remove('access_token');
    await _prefs?.remove('refresh_token');
  }

  // 用户信息
  Future<void> setUserInfo(Map<String, dynamic> user) async {
    await _prefs?.setString('user_info', jsonEncode(user));
  }

  Map<String, dynamic>? getUserInfo() {
    final userStr = _prefs?.getString('user_info');
    if (userStr != null) {
      return jsonDecode(userStr) as Map<String, dynamic>;
    }
    return null;
  }

  Future<void> clearUserInfo() async {
    await _prefs?.remove('user_info');
  }

  // 设置项
  Future<void> setRole(String role) async {
    await _prefs?.setString('user_role', role);
  }

  String? getRole() {
    return _prefs?.getString('user_role');
  }

  Future<void> setMobileUsername(String username) async {
    await _prefs?.setString('mobile_username', username);
  }

  String? getMobileUsername() {
    return _prefs?.getString('mobile_username');
  }

  // 清除所有数据
  Future<void> clearAll() async {
    await _prefs?.clear();
  }

  // 缓存检测历史（离线支持）
  Future<void> cacheHistory(List<Map<String, dynamic>> history) async {
    await _prefs?.setString('cached_history', jsonEncode(history));
  }

  List<Map<String, dynamic>> getCachedHistory() {
    final historyStr = _prefs?.getString('cached_history');
    if (historyStr != null) {
      return List<Map<String, dynamic>>.from(jsonDecode(historyStr));
    }
    return [];
  }
}

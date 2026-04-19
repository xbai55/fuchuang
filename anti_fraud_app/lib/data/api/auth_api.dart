import '../../core/network/api_client.dart';
import '../models/app_user.dart';

class AuthApi {
  final ApiClient _client = ApiClient();

  Future<AppUser> login({
    required String username,
    required String password,
  }) async {
    final data = await _client.loginWithPassword(
      username: username,
      password: password,
    );
    return AppUser.fromJson(data['user'] as Map<String, dynamic>? ?? const {});
  }

  Future<AppUser> register({
    required String username,
    required String email,
    required String password,
  }) async {
    final data = await _client.registerAccount(
      username: username,
      email: email,
      password: password,
    );
    return AppUser.fromJson(data['user'] as Map<String, dynamic>? ?? const {});
  }

  Future<void> logout() => _client.clearSession();
}

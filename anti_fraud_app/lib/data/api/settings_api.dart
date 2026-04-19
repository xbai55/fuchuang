import '../../core/constants/api_constants.dart';
import '../../core/network/api_client.dart';
import '../../core/storage/local_storage.dart';
import '../models/app_user.dart';

class SettingsApi {
  final ApiClient _client = ApiClient();
  final LocalStorage _storage = LocalStorage();

  Future<AppUser> getSettings() async {
    await _client.ensureAuthenticated();
    final response = await _client.get<Map<String, dynamic>>(
      ApiConstants.settings,
    );
    return _saveUser(response ?? const {});
  }

  Future<AppUser> updateSettings(Map<String, dynamic> settings) async {
    await _client.ensureAuthenticated();
    final response = await _client.patch<Map<String, dynamic>>(
      ApiConstants.settings,
      data: settings,
    );
    return _saveUser(response ?? const {});
  }

  Future<AppUser> updateProfile(Map<String, dynamic> profile) async {
    await _client.ensureAuthenticated();
    final response = await _client.put<Map<String, dynamic>>(
      ApiConstants.settingsProfile,
      data: profile,
    );
    return _saveUser(response ?? const {});
  }

  Future<void> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    await _client.ensureAuthenticated();
    await _client.post<void>(
      ApiConstants.settingsChangePassword,
      data: {
        'current_password': currentPassword,
        'new_password': newPassword,
      },
    );
  }

  Future<void> deleteAccount() async {
    await _client.ensureAuthenticated();
    await _client.delete<void>(ApiConstants.settingsAccount);
    await _client.clearSession();
  }

  AppUser? getCachedUser() {
    final user = _storage.getUserInfo();
    if (user == null) return null;
    return AppUser.fromJson(user);
  }

  AppUser _saveUser(Map<String, dynamic> json) {
    final user = AppUser.fromJson(json);
    _storage.setUserInfo(user.toJson());
    return user;
  }
}

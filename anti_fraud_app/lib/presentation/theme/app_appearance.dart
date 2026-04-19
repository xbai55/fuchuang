import 'package:flutter/material.dart';

import '../../core/storage/local_storage.dart';
import '../../data/models/app_user.dart';

class AppAppearance extends ChangeNotifier {
  AppAppearance._();

  static final AppAppearance instance = AppAppearance._();

  String _theme = 'dark';
  String _fontSize = 'medium';
  String _language = 'zh-CN';
  bool _privacyMode = false;

  String get theme => _theme;
  String get fontSize => _fontSize;
  String get language => _language;
  bool get privacyMode => _privacyMode;
  bool get isEnglish => _language == 'en-US';

  bool get isLight {
    if (_theme == 'system') {
      final platformBrightness =
          WidgetsBinding.instance.platformDispatcher.platformBrightness;
      return platformBrightness == Brightness.light;
    }
    return _theme == 'light';
  }

  ThemeMode get themeMode {
    switch (_theme) {
      case 'light':
        return ThemeMode.light;
      case 'system':
        return ThemeMode.system;
      default:
        return ThemeMode.dark;
    }
  }

  double get textScale {
    switch (_fontSize) {
      case 'small':
        return 0.92;
      case 'large':
        return 1.14;
      default:
        return 1.0;
    }
  }

  void loadFromStorage() {
    final user = LocalStorage().getUserInfo();
    if (user == null) return;
    applyUser(AppUser.fromJson(user), notify: false);
  }

  void applyUser(AppUser user, {bool notify = true}) {
    applySettings(
      theme: user.theme,
      fontSize: user.fontSize,
      language: user.language,
      privacyMode: user.privacyMode,
      notify: notify,
    );
  }

  void applySettings({
    String? theme,
    String? fontSize,
    String? language,
    bool? privacyMode,
    bool notify = true,
  }) {
    _theme = theme ?? _theme;
    _fontSize = fontSize ?? _fontSize;
    _language = language ?? _language;
    _privacyMode = privacyMode ?? _privacyMode;
    if (notify) notifyListeners();
  }

  void reset() {
    _theme = 'dark';
    _fontSize = 'medium';
    _language = 'zh-CN';
    _privacyMode = false;
    notifyListeners();
  }
}

import 'package:flutter/services.dart';

class EmergencyActions {
  static const MethodChannel _channel =
      MethodChannel('tianshu_mingyu/emergency_actions');

  static String sanitizePhoneNumber(String value) {
    return value.replaceAll(RegExp(r'[^\d+]'), '');
  }

  static Future<bool> dial(String value) async {
    final number = sanitizePhoneNumber(value);
    if (number.isEmpty) {
      return false;
    }

    try {
      return await _channel.invokeMethod<bool>('dial', {'number': number}) ??
          false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }

  static Future<bool> speak(String text, {required String language}) async {
    if (text.trim().isEmpty) {
      return false;
    }

    try {
      return await _channel.invokeMethod<bool>(
            'speak',
            {'text': text.trim(), 'language': language},
          ) ??
          false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }

  static String buildRiskWarningText({
    required String riskLevel,
    required bool isEnglish,
  }) {
    if (riskLevel == 'high') {
      return isEnglish
          ? 'High-risk fraud warning. Stop transfers and screen sharing immediately. Keep evidence, contact your guardian, or call 96110. In an emergency, call 110.'
          : '\u9ad8\u98ce\u9669\u53cd\u8bc8\u9884\u8b66\u3002\u8bf7\u7acb\u5373\u505c\u6b62\u8f6c\u8d26\u548c\u5171\u4eab\u5c4f\u5e55\uff0c\u4fdd\u7559\u8bc1\u636e\uff0c\u8054\u7cfb\u76d1\u62a4\u4eba\u6216\u62e8\u6253 96110\u3002\u7d27\u6025\u60c5\u51b5\u8bf7\u62e8\u6253 110\u3002';
    }

    return isEnglish
        ? 'Fraud risk detected. Pause the operation, verify the identity, and do not continue payment or provide verification codes. Call 96110 if needed.'
        : '\u68c0\u6d4b\u5230\u8bc8\u9a97\u98ce\u9669\u3002\u8bf7\u6682\u505c\u64cd\u4f5c\uff0c\u6838\u5b9e\u5bf9\u65b9\u8eab\u4efd\uff0c\u4e0d\u8981\u7ee7\u7eed\u4ed8\u6b3e\u6216\u63d0\u4f9b\u9a8c\u8bc1\u7801\u3002\u5982\u6709\u7591\u95ee\u8bf7\u62e8\u6253 96110\u3002';
  }

  static Future<bool> speakRiskWarning({
    required String riskLevel,
    required bool isEnglish,
  }) {
    return speak(
      buildRiskWarningText(riskLevel: riskLevel, isEnglish: isEnglish),
      language: isEnglish ? 'en-US' : 'zh-CN',
    );
  }
}

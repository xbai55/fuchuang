import 'app_appearance.dart';

class AppLocale {
  AppLocale._();

  static String text(String zh, String en) {
    return AppAppearance.instance.isEnglish ? en : zh;
  }
}

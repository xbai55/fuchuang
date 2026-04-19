import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'core/constants/api_constants.dart';
import 'core/network/api_client.dart';
import 'core/storage/local_storage.dart';
import 'presentation/pages/auth/auth_page.dart';
import 'presentation/theme/app_appearance.dart';
import 'presentation/theme/app_locale.dart';
import 'presentation/theme/app_theme.dart';
import 'presentation/pages/main_shell.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // 设置系统UI样式
  SystemChrome.setSystemUIOverlayStyle(
    SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
      systemNavigationBarColor: AppTheme.backgroundColor,
      systemNavigationBarIconBrightness: Brightness.light,
    ),
  );

  // 强制竖屏
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  // 初始化本地存储
  await LocalStorage().init();

  // 初始化 API 客户端
  ApiClient().init();
  AppAppearance.instance.loadFromStorage();

  runApp(const AntiFraudApp());
}

class AntiFraudApp extends StatefulWidget {
  final bool bypassAuth;

  const AntiFraudApp({
    super.key,
    this.bypassAuth = false,
  });

  @override
  State<AntiFraudApp> createState() => _AntiFraudAppState();
}

class _AntiFraudAppState extends State<AntiFraudApp> {
  bool _isAuthenticated = false;

  @override
  void initState() {
    super.initState();
    _isAuthenticated =
        widget.bypassAuth || LocalStorage().getAccessToken() != null;
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: AppAppearance.instance,
      builder: (context, _) {
        return MaterialApp(
          title: ApiConstants.appName,
          debugShowCheckedModeBanner: false,
          theme: AppTheme.lightTheme,
          darkTheme: AppTheme.darkTheme,
          themeMode: AppAppearance.instance.themeMode,
          builder: (context, child) {
            final mediaQuery = MediaQuery.of(context);
            final scaled = mediaQuery.copyWith(
              textScaler: TextScaler.linear(AppAppearance.instance.textScale),
            );
            final content = MediaQuery(data: scaled, child: child!);
            if (!AppAppearance.instance.privacyMode) {
              return content;
            }
            return Stack(
              children: [
                content,
                Positioned(
                  top: mediaQuery.padding.top + 12,
                  right: 70,
                  child: IgnorePointer(
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        color: AppTheme.primaryColor.withValues(alpha: 0.16),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: AppTheme.primaryColor.withValues(alpha: 0.35),
                        ),
                      ),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 6),
                        child: Text(
                          AppLocale.text('隐私模式', 'Privacy'),
                          style: const TextStyle(
                            color: AppTheme.primaryColor,
                            fontSize: 12,
                            fontWeight: FontWeight.w900,
                            decoration: TextDecoration.none,
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            );
          },
          home: _isAuthenticated
              ? MainShell(
                  onLoggedOut: () {
                    AppAppearance.instance.reset();
                    setState(() => _isAuthenticated = false);
                  },
                )
              : AuthPage(
                  onAuthenticated: () {
                    AppAppearance.instance.loadFromStorage();
                    setState(() => _isAuthenticated = true);
                  },
                ),
        );
      },
    );
  }
}

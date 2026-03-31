import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'core/network/api_client.dart';
import 'core/storage/local_storage.dart';
import 'presentation/theme/app_theme.dart';
import 'presentation/pages/main_shell.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // 设置系统UI样式
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
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

  runApp(const AntiFraudApp());
}

class AntiFraudApp extends StatelessWidget {
  const AntiFraudApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AI 反诈助手',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      home: const MainShell(),
    );
  }
}

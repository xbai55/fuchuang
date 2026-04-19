import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import '../theme/app_locale.dart';
import 'home/home_page.dart';
import 'agent/agent_page.dart';
import 'history/history_page.dart';
import 'settings/settings_page.dart';

/// 主壳层页面
/// 包含底部导航栏，切换主要功能模块
class MainShell extends StatefulWidget {
  final VoidCallback onLoggedOut;

  const MainShell({
    super.key,
    required this.onLoggedOut,
  });

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    final pages = [
      const HomePage(),
      const AgentPage(),
      const HistoryPage(),
      SettingsPage(onLoggedOut: widget.onLoggedOut),
    ];

    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: pages,
      ),
      bottomNavigationBar: Container(
        margin: const EdgeInsets.fromLTRB(16, 0, 16, 12),
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
        decoration: BoxDecoration(
          color: AppTheme.surfaceColor.withValues(alpha: 0.96),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: AppTheme.outlineColor),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.25),
              blurRadius: 18,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: SafeArea(
          top: false,
          child: BottomNavigationBar(
            currentIndex: _currentIndex,
            onTap: (index) {
              if (_currentIndex == index) return;
              setState(() => _currentIndex = index);
            },
            backgroundColor: Colors.transparent,
            elevation: 0,
            selectedItemColor: AppTheme.primaryColor,
            unselectedItemColor: Colors.white54,
            selectedLabelStyle: const TextStyle(
              fontWeight: FontWeight.w700,
              fontSize: 12,
            ),
            unselectedLabelStyle: const TextStyle(
              fontSize: 12,
            ),
            iconSize: 24,
            type: BottomNavigationBarType.fixed,
            items: [
              BottomNavigationBarItem(
                icon: const Icon(Icons.security_outlined),
                activeIcon: const Icon(Icons.security),
                label: AppLocale.text('智能检测', 'Detect'),
              ),
              BottomNavigationBarItem(
                icon: const Icon(Icons.smart_toy_outlined),
                activeIcon: const Icon(Icons.smart_toy),
                label: AppLocale.text('反诈助手', 'Assistant'),
              ),
              BottomNavigationBarItem(
                icon: const Icon(Icons.history_outlined),
                activeIcon: const Icon(Icons.history),
                label: AppLocale.text('历史记录', 'History'),
              ),
              BottomNavigationBarItem(
                icon: const Icon(Icons.settings_outlined),
                activeIcon: const Icon(Icons.settings),
                label: AppLocale.text('设置', 'Settings'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

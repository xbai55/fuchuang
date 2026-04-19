import 'package:flutter/material.dart';

import '../../../data/api/auth_api.dart';
import '../../../data/api/settings_api.dart';
import '../../../data/models/app_user.dart';
import '../../theme/app_appearance.dart';
import '../../theme/app_locale.dart';
import '../../theme/app_theme.dart';

class SettingsPage extends StatefulWidget {
  final VoidCallback onLoggedOut;

  const SettingsPage({
    super.key,
    required this.onLoggedOut,
  });

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  final SettingsApi _settingsApi = SettingsApi();
  final AuthApi _authApi = AuthApi();
  final GlobalKey<FormState> _profileFormKey = GlobalKey<FormState>();
  final GlobalKey<FormState> _passwordFormKey = GlobalKey<FormState>();

  final TextEditingController _usernameController = TextEditingController();
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _guardianController = TextEditingController();
  final TextEditingController _currentPasswordController =
      TextEditingController();
  final TextEditingController _newPasswordController = TextEditingController();
  final TextEditingController _confirmPasswordController =
      TextEditingController();

  AppUser? _user;
  bool _loading = true;
  bool _saving = false;
  String _ageGroup = 'unknown';
  String _gender = 'unknown';
  String _occupation = 'other';

  @override
  void initState() {
    super.initState();
    final cached = _settingsApi.getCachedUser();
    if (cached != null) {
      _applyUser(cached);
      _loading = false;
    }
    _loadSettings();
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _emailController.dispose();
    _guardianController.dispose();
    _currentPasswordController.dispose();
    _newPasswordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  Future<void> _loadSettings() async {
    try {
      final user = await _settingsApi.getSettings();
      if (!mounted) return;
      setState(() {
        _applyUser(user);
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _loading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content:
              Text('${AppLocale.text('加载设置失败', 'Failed to load settings')}：$e'),
        ),
      );
    }
  }

  void _applyUser(AppUser user) {
    _user = user;
    AppAppearance.instance.applyUser(user);
    _usernameController.text = user.username;
    _emailController.text = user.email;
    _guardianController.text = user.guardianName;
    _ageGroup = user.ageGroup;
    _gender = user.gender;
    _occupation = user.occupation;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.backgroundColor,
      appBar: AppBar(
        title: Text(AppLocale.text('设置', 'Settings')),
        actions: [
          IconButton(
            tooltip: AppLocale.text('刷新', 'Refresh'),
            icon: const Icon(Icons.refresh),
            onPressed: _loadSettings,
          ),
        ],
      ),
      body: SafeArea(
        child: _loading
            ? const Center(
                child: CircularProgressIndicator(color: AppTheme.primaryColor),
              )
            : ListView(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
                children: [
                  Text(
                    AppLocale.text(
                      '管理账号信息、个性偏好和安全控制。',
                      'Manage account, preferences, and security controls.',
                    ),
                    style: const TextStyle(color: Colors.white60, height: 1.45),
                  ),
                  const SizedBox(height: 16),
                  _buildProfileSection(),
                  const SizedBox(height: 16),
                  _buildAppearanceSection(),
                  const SizedBox(height: 16),
                  _buildNotificationSection(),
                  const SizedBox(height: 16),
                  _buildSecuritySection(),
                ],
              ),
      ),
    );
  }

  Widget _buildProfileSection() {
    return _SettingsCard(
      title: AppLocale.text('个人资料', 'Profile'),
      icon: Icons.person_outline,
      child: Form(
        key: _profileFormKey,
        child: Column(
          children: [
            TextFormField(
              controller: _usernameController,
              decoration:
                  InputDecoration(labelText: AppLocale.text('用户名', 'Username')),
              validator: (value) {
                final text = value?.trim() ?? '';
                if (text.isEmpty) {
                  return AppLocale.text('请输入用户名', 'Please enter username');
                }
                if (text.length < 3) {
                  return AppLocale.text('用户名至少需要 3 个字符',
                      'Username must be at least 3 characters');
                }
                return null;
              },
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _emailController,
              decoration:
                  InputDecoration(labelText: AppLocale.text('邮箱', 'Email')),
              keyboardType: TextInputType.emailAddress,
              validator: (value) {
                final text = value?.trim() ?? '';
                if (text.isEmpty) {
                  return AppLocale.text('请输入邮箱', 'Please enter email');
                }
                if (!text.contains('@') || !text.contains('.')) {
                  return AppLocale.text(
                      '请输入有效的邮箱地址', 'Please enter a valid email');
                }
                return null;
              },
            ),
            const SizedBox(height: 12),
            _buildDropdown(
              label: AppLocale.text('年龄', 'Age Group'),
              value: _ageGroup,
              items: {
                'unknown': AppLocale.text('未设置', 'Unset'),
                'child': AppLocale.text('儿童', 'Child'),
                'young_adult': AppLocale.text('青年', 'Young Adult'),
                'elderly': AppLocale.text('老年', 'Elderly'),
              },
              onChanged: (value) => setState(() => _ageGroup = value),
            ),
            const SizedBox(height: 12),
            _buildDropdown(
              label: AppLocale.text('性别', 'Gender'),
              value: _gender,
              items: {
                'unknown': AppLocale.text('未设置', 'Unset'),
                'male': AppLocale.text('男', 'Male'),
                'female': AppLocale.text('女', 'Female'),
              },
              onChanged: (value) => setState(() => _gender = value),
            ),
            const SizedBox(height: 12),
            _buildDropdown(
              label: AppLocale.text('职业', 'Occupation'),
              value: _occupation,
              items: {
                'student': AppLocale.text('学生', 'Student'),
                'enterprise_staff': AppLocale.text('企业职员', 'Enterprise Staff'),
                'self_employed': AppLocale.text('个体经营者', 'Self-employed'),
                'retired_group': AppLocale.text('退休人群', 'Retired'),
                'public_officer': AppLocale.text('公职人员', 'Public Officer'),
                'finance_practitioner':
                    AppLocale.text('金融从业者', 'Finance Practitioner'),
                'other': AppLocale.text('其他', 'Other'),
              },
              onChanged: (value) => setState(() => _occupation = value),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _guardianController,
              decoration: InputDecoration(
                  labelText: AppLocale.text('监护人姓名', 'Guardian Name')),
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _saving ? null : _saveProfile,
                child: Text(AppLocale.text('保存资料', 'Save Profile')),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAppearanceSection() {
    final user = _user;
    return _SettingsCard(
      title: AppLocale.text('外观', 'Appearance'),
      icon: Icons.palette_outlined,
      child: Column(
        children: [
          _ChoiceRow(
            title: AppLocale.text('主题', 'Theme'),
            value: user?.theme ?? 'dark',
            options: {
              'dark': AppLocale.text('深色', 'Dark'),
              'light': AppLocale.text('浅色', 'Light'),
              'system': AppLocale.text('跟随系统', 'System'),
            },
            onSelected: (value) => _updateSetting(
                {'theme': value}, AppLocale.text('主题已更新', 'Theme updated')),
          ),
          const SizedBox(height: 14),
          _ChoiceRow(
            title: AppLocale.text('语言', 'Language'),
            value: user?.language ?? 'zh-CN',
            options: const {'zh-CN': '中文', 'en-US': 'English'},
            onSelected: (value) => _updateSetting({'language': value},
                AppLocale.text('语言已更新', 'Language updated')),
          ),
          const SizedBox(height: 14),
          _ChoiceRow(
            title: AppLocale.text('字体大小', 'Font Size'),
            value: user?.fontSize ?? 'medium',
            options: {
              'small': AppLocale.text('小', 'Small'),
              'medium': AppLocale.text('中', 'Medium'),
              'large': AppLocale.text('大', 'Large'),
            },
            onSelected: (value) => _updateSetting({'font_size': value},
                AppLocale.text('字体大小已更新', 'Font size updated')),
          ),
          const SizedBox(height: 8),
          _SwitchTile(
            title: AppLocale.text('隐私模式', 'Privacy Mode'),
            subtitle: AppLocale.text('尽可能在界面中隐藏敏感信息。',
                'Hide sensitive information on the interface when possible.'),
            value: user?.privacyMode ?? false,
            onChanged: (value) => _updateSetting({'privacy_mode': value},
                AppLocale.text('隐私模式已更新', 'Privacy mode updated')),
          ),
        ],
      ),
    );
  }

  Widget _buildNotificationSection() {
    final user = _user;
    final enabled = user?.notifyEnabled ?? true;
    return _SettingsCard(
      title: AppLocale.text('通知', 'Notifications'),
      icon: Icons.notifications_none,
      child: Column(
        children: [
          _SwitchTile(
            title: AppLocale.text('启用通知', 'Enable Notifications'),
            subtitle: AppLocale.text(
                '通知推送的总开关。', 'Master switch for notification delivery.'),
            value: enabled,
            onChanged: (value) => _updateSetting({'notify_enabled': value},
                AppLocale.text('通知设置已更新', 'Notification settings updated')),
          ),
          _SwitchTile(
            title: AppLocale.text('高风险提醒', 'High-risk Alerts'),
            subtitle: AppLocale.text('检测结果为高风险时发送额外提醒。',
                'Send extra alerts when risk level is high.'),
            value: user?.notifyHighRisk ?? true,
            enabled: enabled,
            onChanged: (value) => _updateSetting({'notify_high_risk': value},
                AppLocale.text('高风险提醒已更新', 'High-risk alert setting updated')),
          ),
          _SwitchTile(
            title: AppLocale.text('监护提醒', 'Guardian Alerts'),
            subtitle: AppLocale.text('需要升级处理时通知监护流程。',
                'Notify guardian workflow when escalation is needed.'),
            value: user?.notifyGuardianAlert ?? true,
            enabled: enabled,
            onChanged: (value) => _updateSetting(
              {'notify_guardian_alert': value},
              AppLocale.text('监护提醒已更新', 'Guardian alert setting updated'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSecuritySection() {
    return _SettingsCard(
      title: AppLocale.text('安全', 'Security'),
      icon: Icons.shield_outlined,
      child: Form(
        key: _passwordFormKey,
        child: Column(
          children: [
            TextFormField(
              controller: _currentPasswordController,
              obscureText: true,
              decoration: InputDecoration(
                  labelText: AppLocale.text('当前密码', 'Current Password')),
              validator: (value) => (value ?? '').isEmpty
                  ? AppLocale.text('请输入当前密码', 'Please enter current password')
                  : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _newPasswordController,
              obscureText: true,
              decoration: InputDecoration(
                  labelText: AppLocale.text('新密码', 'New Password')),
              validator: (value) {
                final text = value ?? '';
                if (text.isEmpty) {
                  return AppLocale.text('请输入新密码', 'Please enter new password');
                }
                if (text.length < 6) {
                  return AppLocale.text(
                      '密码至少需要 6 个字符', 'Password must be at least 6 characters');
                }
                return null;
              },
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _confirmPasswordController,
              obscureText: true,
              decoration: InputDecoration(
                  labelText: AppLocale.text('确认新密码', 'Confirm New Password')),
              validator: (value) {
                if ((value ?? '').isEmpty) {
                  return AppLocale.text(
                      '请再次输入新密码', 'Please confirm new password');
                }
                if (value != _newPasswordController.text) {
                  return AppLocale.text('两次密码不一致', 'Passwords do not match');
                }
                return null;
              },
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _saving ? null : _changePassword,
                child: Text(AppLocale.text('修改密码', 'Change Password')),
              ),
            ),
            const SizedBox(height: 14),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _saving ? null : _logout,
                    icon: const Icon(Icons.logout),
                    label: Text(AppLocale.text('退出登录', 'Log Out')),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _saving ? null : _confirmDeleteAccount,
                    icon: const Icon(Icons.delete_outline),
                    label: Text(AppLocale.text('注销账号', 'Delete Account')),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppTheme.errorColor,
                      side: const BorderSide(color: AppTheme.errorColor),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDropdown({
    required String label,
    required String value,
    required Map<String, String> items,
    required ValueChanged<String> onChanged,
  }) {
    return DropdownButtonFormField<String>(
      initialValue: items.containsKey(value) ? value : items.keys.first,
      decoration: InputDecoration(labelText: label),
      dropdownColor: AppTheme.surfaceColorLight,
      items: items.entries
          .map(
            (entry) => DropdownMenuItem<String>(
              value: entry.key,
              child: Text(entry.value),
            ),
          )
          .toList(),
      onChanged: (value) {
        if (value != null) onChanged(value);
      },
    );
  }

  Future<void> _saveProfile() async {
    if (!_profileFormKey.currentState!.validate()) return;
    await _runSave(() async {
      final user = await _settingsApi.updateProfile({
        'username': _usernameController.text.trim(),
        'email': _emailController.text.trim(),
        'age_group': _ageGroup,
        'gender': _gender,
        'occupation': _occupation,
        'guardian_name': _guardianController.text.trim(),
      });
      setState(() => _applyUser(user));
      _showMessage(AppLocale.text('资料已更新', 'Profile updated'));
    });
  }

  Future<void> _updateSetting(
    Map<String, dynamic> patch,
    String successText,
  ) async {
    await _runSave(() async {
      final user = await _settingsApi.updateSettings(patch);
      setState(() => _applyUser(user));
      _showMessage(successText);
    });
  }

  Future<void> _changePassword() async {
    if (!_passwordFormKey.currentState!.validate()) return;
    await _runSave(() async {
      await _settingsApi.changePassword(
        currentPassword: _currentPasswordController.text,
        newPassword: _newPasswordController.text,
      );
      _currentPasswordController.clear();
      _newPasswordController.clear();
      _confirmPasswordController.clear();
      _showMessage(AppLocale.text('密码修改成功', 'Password changed successfully'));
    });
  }

  Future<void> _runSave(Future<void> Function() action) async {
    setState(() => _saving = true);
    try {
      await action();
    } catch (e) {
      if (!mounted) return;
      _showMessage('${AppLocale.text('操作失败', 'Operation failed')}：$e');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _logout() async {
    await _authApi.logout();
    if (!mounted) return;
    widget.onLoggedOut();
  }

  Future<void> _confirmDeleteAccount() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppTheme.surfaceColor,
        title: Text(AppLocale.text('注销账号？', 'Delete account?')),
        content: Text(
          AppLocale.text(
            '你将失去与该账号关联的个人设置、联系人数据和聊天历史。',
            'You will lose profile settings, contacts, and chat history tied to this account.',
          ),
          style: const TextStyle(color: Colors.white70, height: 1.45),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(AppLocale.text('取消', 'Cancel')),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.errorColor,
              foregroundColor: Colors.white,
            ),
            child: Text(AppLocale.text('确认注销', 'Delete')),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    await _runSave(() async {
      await _settingsApi.deleteAccount();
      if (!mounted) return;
      widget.onLoggedOut();
    });
  }

  void _showMessage(String text) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  }
}

class _SettingsCard extends StatelessWidget {
  final String title;
  final IconData icon;
  final Widget child;

  const _SettingsCard({
    required this.title,
    required this.icon,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surfaceColor,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.outlineColor),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: AppTheme.primaryColor),
              const SizedBox(width: 10),
              Text(
                title,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          child,
        ],
      ),
    );
  }
}

class _ChoiceRow extends StatelessWidget {
  final String title;
  final String value;
  final Map<String, String> options;
  final ValueChanged<String> onSelected;

  const _ChoiceRow({
    required this.title,
    required this.value,
    required this.options,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: const TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 10),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: options.entries.map((entry) {
            final selected = entry.key == value;
            return ChoiceChip(
              selected: selected,
              label: Text(entry.value),
              labelStyle: TextStyle(
                color: selected ? const Color(0xFF04201C) : Colors.white70,
                fontWeight: FontWeight.w700,
              ),
              selectedColor: AppTheme.primaryColor,
              backgroundColor: AppTheme.surfaceColorLight,
              side: BorderSide(color: AppTheme.outlineColor),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
              onSelected: (_) => onSelected(entry.key),
            );
          }).toList(),
        ),
      ],
    );
  }
}

class _SwitchTile extends StatelessWidget {
  final String title;
  final String subtitle;
  final bool value;
  final bool enabled;
  final ValueChanged<bool> onChanged;

  const _SwitchTile({
    required this.title,
    required this.subtitle,
    required this.value,
    this.enabled = true,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return SwitchListTile(
      contentPadding: EdgeInsets.zero,
      value: value,
      activeThumbColor: AppTheme.primaryColor,
      onChanged: enabled ? onChanged : null,
      title: Text(
        title,
        style: const TextStyle(
          color: Colors.white,
          fontWeight: FontWeight.w800,
        ),
      ),
      subtitle: Text(
        subtitle,
        style: const TextStyle(color: Colors.white60, height: 1.35),
      ),
    );
  }
}

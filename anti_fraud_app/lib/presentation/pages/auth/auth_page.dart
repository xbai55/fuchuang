import 'package:flutter/material.dart';

import '../../../core/constants/api_constants.dart';
import '../../../data/api/auth_api.dart';
import '../../theme/app_appearance.dart';
import '../../theme/app_locale.dart';
import '../../theme/app_theme.dart';

class AuthPage extends StatefulWidget {
  final VoidCallback onAuthenticated;

  const AuthPage({
    super.key,
    required this.onAuthenticated,
  });

  @override
  State<AuthPage> createState() => _AuthPageState();
}

class _AuthPageState extends State<AuthPage> {
  final AuthApi _authApi = AuthApi();
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();
  final TextEditingController _usernameController = TextEditingController();
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  final TextEditingController _confirmPasswordController =
      TextEditingController();

  bool _isRegister = false;
  bool _isLoading = false;
  bool _obscurePassword = true;

  @override
  void dispose() {
    _usernameController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.backgroundColor,
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              const Color(0xFF0D211D),
              AppTheme.backgroundColor,
              AppTheme.backgroundColor,
            ],
          ),
        ),
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(24, 36, 24, 28),
            children: [
              _buildBrand(),
              const SizedBox(height: 28),
              _buildFormCard(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildBrand() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 64,
          height: 64,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(8),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.16),
                blurRadius: 18,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          clipBehavior: Clip.antiAlias,
          child: Image.asset(
            'assets/images/fclogo.png',
            fit: BoxFit.cover,
          ),
        ),
        const SizedBox(height: 18),
        const Text(
          ApiConstants.appName,
          style: TextStyle(
            color: Colors.white,
            fontSize: 30,
            fontWeight: FontWeight.w900,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          AppLocale.text(
            '登录后同步检测历史、反诈助手对话和个人安全设置。',
            'Sign in to sync detection history, assistant chats, and security settings.',
          ),
          style:
              const TextStyle(color: Colors.white60, height: 1.5, fontSize: 15),
        ),
      ],
    );
  }

  Widget _buildFormCard() {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppTheme.surfaceColor,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.outlineColor),
      ),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: _AuthTabButton(
                    label: AppLocale.text('登录', 'Sign In'),
                    selected: !_isRegister,
                    onTap: () => setState(() => _isRegister = false),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _AuthTabButton(
                    label: AppLocale.text('注册', 'Register'),
                    selected: _isRegister,
                    onTap: () => setState(() => _isRegister = true),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            TextFormField(
              controller: _usernameController,
              textInputAction: TextInputAction.next,
              decoration: InputDecoration(
                labelText: AppLocale.text('用户名', 'Username'),
                prefixIcon: const Icon(Icons.person_outline),
              ),
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
            if (_isRegister) ...[
              const SizedBox(height: 14),
              TextFormField(
                controller: _emailController,
                keyboardType: TextInputType.emailAddress,
                textInputAction: TextInputAction.next,
                decoration: InputDecoration(
                  labelText: AppLocale.text('邮箱', 'Email'),
                  prefixIcon: const Icon(Icons.mail_outline),
                ),
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
            ],
            const SizedBox(height: 14),
            TextFormField(
              controller: _passwordController,
              obscureText: _obscurePassword,
              textInputAction:
                  _isRegister ? TextInputAction.next : TextInputAction.done,
              decoration: InputDecoration(
                labelText: AppLocale.text('密码', 'Password'),
                prefixIcon: const Icon(Icons.lock_outline),
                suffixIcon: IconButton(
                  onPressed: () {
                    setState(() => _obscurePassword = !_obscurePassword);
                  },
                  icon: Icon(
                    _obscurePassword
                        ? Icons.visibility_outlined
                        : Icons.visibility_off_outlined,
                  ),
                ),
              ),
              validator: (value) {
                final text = value ?? '';
                if (text.isEmpty) {
                  return AppLocale.text('请输入密码', 'Please enter password');
                }
                if (_isRegister && text.length < 6) {
                  return AppLocale.text(
                      '密码至少需要 6 个字符', 'Password must be at least 6 characters');
                }
                return null;
              },
              onFieldSubmitted: (_) {
                if (!_isRegister) _submit();
              },
            ),
            if (_isRegister) ...[
              const SizedBox(height: 14),
              TextFormField(
                controller: _confirmPasswordController,
                obscureText: _obscurePassword,
                textInputAction: TextInputAction.done,
                decoration: InputDecoration(
                  labelText: AppLocale.text('确认密码', 'Confirm Password'),
                  prefixIcon: const Icon(Icons.lock_reset_outlined),
                ),
                validator: (value) {
                  if ((value ?? '').isEmpty) {
                    return AppLocale.text('请再次输入密码', 'Please confirm password');
                  }
                  if (value != _passwordController.text) {
                    return AppLocale.text('两次密码不一致', 'Passwords do not match');
                  }
                  return null;
                },
                onFieldSubmitted: (_) => _submit(),
              ),
            ],
            const SizedBox(height: 22),
            ElevatedButton(
              onPressed: _isLoading ? null : _submit,
              child: _isLoading
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Color(0xFF04201C),
                      ),
                    )
                  : Text(_isRegister
                      ? AppLocale.text('注册', 'Register')
                      : AppLocale.text('登录', 'Sign In')),
            ),
            const SizedBox(height: 14),
            TextButton(
              onPressed: _isLoading
                  ? null
                  : () => setState(() => _isRegister = !_isRegister),
              child: Text(_isRegister
                  ? AppLocale.text(
                      '已有账号？去登录', 'Already have an account? Sign in')
                  : AppLocale.text('还没有账号？去注册', 'No account yet? Register')),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isLoading = true);
    try {
      if (_isRegister) {
        final user = await _authApi.register(
          username: _usernameController.text.trim(),
          email: _emailController.text.trim(),
          password: _passwordController.text,
        );
        AppAppearance.instance.applyUser(user);
      } else {
        final user = await _authApi.login(
          username: _usernameController.text.trim(),
          password: _passwordController.text,
        );
        AppAppearance.instance.applyUser(user);
      }

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(_isRegister
              ? AppLocale.text('注册成功', 'Registered successfully')
              : AppLocale.text('登录成功', 'Signed in successfully')),
        ),
      );
      widget.onAuthenticated();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            '${_isRegister ? AppLocale.text('注册', 'Register') : AppLocale.text('登录', 'Sign In')}${AppLocale.text('失败', ' failed')}：$e',
          ),
        ),
      );
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }
}

class _AuthTabButton extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _AuthTabButton({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(8),
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: selected
              ? AppTheme.primaryColor
              : Colors.white.withValues(alpha: 0.04),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: selected ? AppTheme.primaryColor : AppTheme.outlineColor,
          ),
        ),
        child: Text(
          label,
          textAlign: TextAlign.center,
          style: TextStyle(
            color: selected ? const Color(0xFF04201C) : Colors.white70,
            fontWeight: FontWeight.w900,
          ),
        ),
      ),
    );
  }
}

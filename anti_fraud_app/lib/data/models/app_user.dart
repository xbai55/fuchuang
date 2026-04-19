class AppUser {
  final int id;
  final String username;
  final String email;
  final String userRole;
  final String ageGroup;
  final String gender;
  final String occupation;
  final String guardianName;
  final String theme;
  final bool notifyEnabled;
  final bool notifyHighRisk;
  final bool notifyGuardianAlert;
  final String language;
  final String fontSize;
  final bool privacyMode;

  const AppUser({
    required this.id,
    required this.username,
    required this.email,
    required this.userRole,
    required this.ageGroup,
    required this.gender,
    required this.occupation,
    required this.guardianName,
    required this.theme,
    required this.notifyEnabled,
    required this.notifyHighRisk,
    required this.notifyGuardianAlert,
    required this.language,
    required this.fontSize,
    required this.privacyMode,
  });

  factory AppUser.fromJson(Map<String, dynamic> json) {
    return AppUser(
      id: (json['id'] as num?)?.toInt() ?? 0,
      username: json['username'] as String? ?? '',
      email: json['email'] as String? ?? '',
      userRole: json['user_role'] as String? ?? 'general',
      ageGroup: json['age_group'] as String? ?? 'unknown',
      gender: json['gender'] as String? ?? 'unknown',
      occupation: json['occupation'] as String? ?? 'other',
      guardianName: json['guardian_name'] as String? ?? '',
      theme: json['theme'] as String? ?? 'dark',
      notifyEnabled: json['notify_enabled'] as bool? ?? true,
      notifyHighRisk: json['notify_high_risk'] as bool? ?? true,
      notifyGuardianAlert: json['notify_guardian_alert'] as bool? ?? true,
      language: json['language'] as String? ?? 'zh-CN',
      fontSize: json['font_size'] as String? ?? 'medium',
      privacyMode: json['privacy_mode'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'username': username,
      'email': email,
      'user_role': userRole,
      'age_group': ageGroup,
      'gender': gender,
      'occupation': occupation,
      'guardian_name': guardianName,
      'theme': theme,
      'notify_enabled': notifyEnabled,
      'notify_high_risk': notifyHighRisk,
      'notify_guardian_alert': notifyGuardianAlert,
      'language': language,
      'font_size': fontSize,
      'privacy_mode': privacyMode,
    };
  }
}

/// 检测结果模型
class DetectionResult {
  final int riskScore;
  final String riskLevel;
  final String scamType;
  final String warningMessage;
  final String finalReport;
  final bool guardianAlert;
  final List<String> actionItems;
  final List<EscalationAction> escalationActions;

  DetectionResult({
    required this.riskScore,
    required this.riskLevel,
    required this.scamType,
    required this.warningMessage,
    required this.finalReport,
    required this.guardianAlert,
    this.actionItems = const [],
    this.escalationActions = const [],
  });

  factory DetectionResult.fromJson(Map<String, dynamic> json) {
    return DetectionResult(
      riskScore: (json['risk_score'] as num?)?.toInt() ?? 0,
      riskLevel: json['risk_level'] as String? ?? 'low',
      scamType: json['scam_type'] as String? ?? '',
      warningMessage: json['warning_message'] as String? ?? '',
      finalReport: json['final_report'] as String? ?? '',
      guardianAlert: json['guardian_alert'] as bool? ?? false,
      actionItems: _parseStringList(json['action_items']),
      escalationActions: _parseEscalationActions(json['escalation_actions']),
    );
  }

  static List<String> _parseStringList(Object? value) {
    if (value is! List) {
      return const [];
    }

    return value
        .map((item) => item.toString().trim())
        .where((item) => item.isNotEmpty)
        .toList(growable: false);
  }

  static List<EscalationAction> _parseEscalationActions(Object? value) {
    if (value is! List) {
      return const [];
    }

    return value
        .whereType<Map>()
        .map((item) => EscalationAction.fromJson(Map<String, dynamic>.from(item)))
        .where((item) => item.value.isNotEmpty)
        .toList(growable: false);
  }

  /// 是否为高风险
  bool get isHighRisk => riskLevel == 'high';

  /// 是否为中风险
  bool get isMediumRisk => riskLevel == 'medium';

  /// 是否为低风险
  bool get isLowRisk => riskLevel == 'low';

  EscalationAction? get guardianCallAction {
    for (final action in escalationActions) {
      final type = action.type.toLowerCase();
      if ((type.contains('guardian') ||
              type.contains('contact') ||
              type.contains('phone')) &&
          action.hasCallablePhone) {
        return action;
      }
    }
    return null;
  }

  /// 获取风险等级显示文本
  String get riskLevelText {
    switch (riskLevel) {
      case 'high':
        return '高风险';
      case 'medium':
        return '中风险';
      case 'low':
        return '低风险';
      default:
        return '未知';
    }
  }

  /// 获取风险等级颜色（用于 UI）
  String get riskColorHex {
    switch (riskLevel) {
      case 'high':
        return '#FF4444';
      case 'medium':
        return '#FF8800';
      case 'low':
        return '#44AA44';
      default:
        return '#888888';
    }
  }
}

class EscalationAction {
  final String type;
  final String label;
  final String value;

  const EscalationAction({
    required this.type,
    required this.label,
    required this.value,
  });

  factory EscalationAction.fromJson(Map<String, dynamic> json) {
    return EscalationAction(
      type: json['type']?.toString() ?? '',
      label: json['label']?.toString() ?? '',
      value: json['value']?.toString() ?? '',
    );
  }

  String get phoneNumber => value.replaceAll(RegExp(r'[^\d+]'), '');

  bool get hasCallablePhone => !value.contains('@') && phoneNumber.length >= 3;
}

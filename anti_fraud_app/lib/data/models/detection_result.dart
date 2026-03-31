/// 检测结果模型
class DetectionResult {
  final int riskScore;
  final String riskLevel;
  final String scamType;
  final String warningMessage;
  final String finalReport;
  final bool guardianAlert;

  DetectionResult({
    required this.riskScore,
    required this.riskLevel,
    required this.scamType,
    required this.warningMessage,
    required this.finalReport,
    required this.guardianAlert,
  });

  factory DetectionResult.fromJson(Map<String, dynamic> json) {
    return DetectionResult(
      riskScore: json['risk_score'] as int,
      riskLevel: json['risk_level'] as String,
      scamType: json['scam_type'] as String,
      warningMessage: json['warning_message'] as String,
      finalReport: json['final_report'] as String,
      guardianAlert: json['guardian_alert'] as bool,
    );
  }

  /// 是否为高风险
  bool get isHighRisk => riskLevel == 'high';

  /// 是否为中风险
  bool get isMediumRisk => riskLevel == 'medium';

  /// 是否为低风险
  bool get isLowRisk => riskLevel == 'low';

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

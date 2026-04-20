import type { FraudAlertPayload, FraudDetectionResponse, RiskLevel } from '../types';

const riskTitles: Record<RiskLevel, string> = {
  low: '安全提醒',
  medium: '疑似诈骗预警',
  high: '高危诈骗拦截提醒',
};

const riskSummaries: Record<RiskLevel, string> = {
  low: '当前内容没有出现强烈的诈骗特征，但系统建议继续保护个人敏感信息，避免被后续话术诱导。',
  medium: '系统已经识别出多项异常模式，存在较高的诱导转账、下载陌生应用或泄露身份信息的风险。',
  high: '系统检测到高度匹配的诈骗脚本，若继续互动或转账，存在明显资金损失与个人信息泄露风险。',
};

const riskRecommendations: Record<RiskLevel, string[]> = {
  low: [
    '继续保护验证码、银行卡号和身份证信息。',
    '如对方开始催促转账或点击链接，请立即重新检测。',
    '优先通过官方渠道核验对方身份。',
  ],
  medium: [
    '暂停当前聊天或交易，不要继续提供敏感信息。',
    '通过平台官网、官方电话或熟人侧渠道复核身份。',
    '保留聊天截图和链接，必要时向平台、老师或家人求证。',
  ],
  high: [
    '立即停止转账、授权登录或输入验证码。',
    '不要点击陌生链接，也不要下载对方提供的软件。',
    '保留证据并尽快联系平台官方、警方或可信联系人协助处理。',
  ],
};

export function shouldShowFraudAlert(response: FraudDetectionResponse): boolean {
  if (response.critical_guardrail_triggered) {
    return true;
  }
  if (response.popup_severity === 'blocking' || response.popup_severity === 'soft') {
    return true;
  }
  if (response.popup_severity === 'none') {
    return Boolean(response.guardian_alert);
  }
  return response.risk_level === 'high' || response.risk_level === 'medium' || response.guardian_alert;
}

export function shouldTriggerFraudVoiceAlert(response: FraudDetectionResponse): boolean {
  if (response.critical_guardrail_triggered) {
    return true;
  }
  if (response.popup_severity === 'blocking') {
    return true;
  }
  return response.risk_level === 'high';
}

export function buildFraudAlertPayload(response: FraudDetectionResponse): FraudAlertPayload {
  const recommendations = [...riskRecommendations[response.risk_level]];
  const hardRuleCount = response.hard_rule_ids?.length ?? 0;
  const softRuleCount = response.soft_rule_ids?.length ?? 0;
  const evidence = [
    `风险评分 ${response.risk_score}/100`,
    `识别诈骗类型：${response.scam_type || '待确认类型'}`,
    response.guardian_alert ? '已达到重点联系人联动阈值' : '暂未触发重点联系人联动',
  ];

  if (hardRuleCount > 0 || softRuleCount > 0) {
    evidence.push(`命中规则：硬红线 ${hardRuleCount} 条，软信号 ${softRuleCount} 条`);
  }

  if (response.guardian_alert) {
    recommendations.push('系统已判定需要重点联系人联动，建议立即同步风险情况。');
  }

  return {
    title: riskTitles[response.risk_level],
    riskScore: response.risk_score,
    riskLevel: response.risk_level,
    scamType: response.scam_type || '待确认类型',
    summary: riskSummaries[response.risk_level],
    warningMessage: response.warning_message,
    evidence,
    recommendations,
    guardianAlert: response.guardian_alert,
    finalReport: response.final_report,
  };
}

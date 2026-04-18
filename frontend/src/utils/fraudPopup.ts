import type { FraudAlertPayload, FraudDetectionResponse, RiskLevel } from '../types';

const riskTitles: Record<RiskLevel, string> = {
  low: '安全提醒',
  medium: '疑似诈骗预警',
  high: '高危诈骗拦截提醒',
};

const riskSummaries: Record<RiskLevel, string> = {
  low: '当前内容没有出现强烈的诈骗特征，但系统建议继续保护个人敏感信息，避免被后续话术诱导。',
  medium: '系统已经识别出多项异常模式，存在较高诱导转账、下载陌生应用或泄露身份信息的风险。',
  high: '系统检测到高度匹配的诈骗剧本，若继续交互或转账，存在明显资金损失与个人信息泄露风险。',
};

const riskRecommendations: Record<RiskLevel, string[]> = {
  low: [
    '保持对验证码、银行卡号和身份证信息的保护。',
    '如对方开始催促转账或点击链接，立即重新检测。',
    '优先通过官方渠道核验对方身份。',
  ],
  medium: [
    '暂停当前聊天或交易，不要继续提供敏感信息。',
    '通过平台官网、官方电话或熟人侧渠道复核身份。',
    '保留聊天截图和链接，必要时向平台或老师家人求证。',
  ],
  high: [
    '立即停止转账、授权登录或验证码输入操作。',
    '不要点击陌生链接，也不要下载对方提供的软件。',
    '保留证据并尽快联系平台官方、警方或监护人协助处理。',
  ],
};

export function shouldShowFraudAlert(response: FraudDetectionResponse): boolean {
  return response.risk_score >= 40 || response.guardian_alert;
}

// 未来正式接入 detect 接口时，直接把后端返回值映射成弹窗展示数据即可。
export function buildFraudAlertPayload(response: FraudDetectionResponse): FraudAlertPayload {
  const recommendations = [...riskRecommendations[response.risk_level]];

  if (response.guardian_alert) {
    recommendations.push('系统已判定需要监护人联动，建议立刻同步风险情况。');
  }

  return {
    title: riskTitles[response.risk_level],
    riskScore: response.risk_score,
    riskLevel: response.risk_level,
    scamType: response.scam_type || '待确认类型',
    summary: riskSummaries[response.risk_level],
    warningMessage: response.warning_message,
    evidence: [
      `风险评分 ${response.risk_score}/100`,
      `识别诈骗类型：${response.scam_type || '待确认类型'}`,
      response.guardian_alert ? '已达到监护人联动阈值' : '暂未触发监护人联动',
    ],
    recommendations,
    guardianAlert: response.guardian_alert,
    finalReport: response.final_report,
  };
}

import { useState } from 'react';
import { AlertOutlined, ApiOutlined, ArrowLeftOutlined, EyeOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { Button, Layout, Space, Typography, message } from 'antd';
import { Link } from 'react-router-dom';
import FraudAlertModal from '../components/FraudAlertModal';
import { buildFraudAlertPayload, shouldShowFraudAlert } from '../utils/fraudPopup';
import { openOfficialPoliceHelpPage } from '../utils/emergencyActions';
import type { FraudAlertPayload, FraudDetectionResponse } from '../types';

const { Content } = Layout;
const { Paragraph, Title, Text } = Typography;

const demoResponses: Array<{
  key: string;
  label: string;
  description: string;
  response: FraudDetectionResponse;
}> = [
  {
    key: 'low',
    label: '低风险样例',
    description: '保留谨慎提示，帮助用户在没有强风险信号时继续核验信息来源。',
    response: {
      risk_score: 26,
      risk_level: 'low',
      scam_type: '信息核验中',
      warning_message: '当前未发现明显诈骗脚本，但仍建议不要透露验证码、银行卡号和身份证信息。',
      final_report: '# 低风险报告\n\n当前未发现明显高危诈骗信号，建议继续通过官方渠道核验对方身份。',
      guardian_alert: false,
    },
  },
  {
    key: 'medium',
    label: '中风险样例',
    description: '展示明显异常的提示层级，强调暂停操作和二次核验。',
    response: {
      risk_score: 68,
      risk_level: 'medium',
      scam_type: '冒充客服退款',
      warning_message:
        '检测到“退款补偿”“下载会议软件”“屏幕共享”等组合话术。\n\n- 暂停当前操作\n- 不要继续输入验证码\n- 通过官方热线核验身份',
      final_report:
        '# 中风险报告\n\n对话中出现退款、远程协助和验证码要求，存在明显诱导风险，建议立即切换到官方渠道复核。',
      guardian_alert: false,
      soft_rule_ids: ['refund-flow', 'remote-control-request'],
    },
  },
  {
    key: 'high',
    label: '高风险样例',
    description: '强提醒风格，附带可信联系人联动按钮和完整报告入口。',
    response: {
      risk_score: 92,
      risk_level: 'high',
      scam_type: '冒充公检法',
      warning_message:
        '检测到“安全账户”“立即转账”“案件保密”等高危组合，疑似冒充公检法诈骗。\n\n1. 立即停止转账\n2. 不要共享屏幕或验证码\n3. 联系可信联系人或拨打 96110',
      final_report:
        '# 高风险报告\n\n该内容与典型冒充公检法诈骗高度相似，存在明显资金损失风险，建议立刻中断联系并同步可信联系人。',
      guardian_alert: true,
      hard_rule_ids: ['safe-account-transfer'],
      popup_severity: 'blocking',
      critical_guardrail_triggered: true,
    },
  },
];

const integrationExample = `const response = await fraudAPI.detect({ message });

if (shouldShowFraudAlert(response)) {
  const popupData = buildFraudAlertPayload(response);
  setAlert(popupData);
  setPopupOpen(true);
}`;

export default function PopupDemo() {
  const [activeAlert, setActiveAlert] = useState<FraudAlertPayload | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const openDemo = (response: FraudDetectionResponse) => {
    const popupData = buildFraudAlertPayload(response);
    setActiveAlert(popupData);
    setModalOpen(true);
  };

  return (
    <Layout className="app-shell min-h-screen">
      <Content className="px-6 py-10">
        <div className="mx-auto max-w-6xl space-y-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="space-y-3">
              <Space size="middle" wrap>
                <span className="inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-4 py-1 text-sm text-indigo-300">
                  <ThunderboltOutlined />
                  预警弹窗演示
                </span>
                <span className="inline-flex items-center gap-2 rounded-full border border-gray-700 bg-[#1b1d34] px-4 py-1 text-sm text-slate-300">
                  <ApiOutlined />
                  与后端返回结构对齐
                </span>
              </Space>
              <Title level={1} style={{ color: '#ffffff', margin: 0 }}>
                风险弹窗与联动反馈
              </Title>
              <Paragraph style={{ color: '#94a3b8', maxWidth: 760, marginBottom: 0 }}>
                这里用静态样例复刻 `FraudDetectionResponse` 到弹窗展示层的映射，方便校验预警层级、
                重点联系人联动、完整报告入口和前端交互细节。
              </Paragraph>
            </div>

            <Link to="/">
              <Button icon={<ArrowLeftOutlined />}>返回主界面</Button>
            </Link>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            {demoResponses.map((item) => {
              const shouldPopup = shouldShowFraudAlert(item.response);

              return (
                <div key={item.key} className="card-dark p-5">
                  <div className="mb-4 flex items-center gap-2 text-white">
                    <AlertOutlined />
                    <span className="font-medium">{item.label}</span>
                  </div>
                  <Paragraph style={{ color: '#94a3b8', minHeight: 44 }}>
                    {item.description}
                  </Paragraph>
                  <div className="mb-4 rounded-xl border border-gray-700 bg-[#18182d] p-3 text-sm text-slate-300">
                    风险评分：{item.response.risk_score}
                    <br />
                    诈骗类型：{item.response.scam_type}
                    <br />
                    是否触发弹窗：{shouldPopup ? '是' : '否'}
                  </div>
                  <Button
                    type="primary"
                    icon={<EyeOutlined />}
                    className="btn-primary w-full"
                    onClick={() => openDemo(item.response)}
                  >
                    打开弹窗预览
                  </Button>
                </div>
              );
            })}
          </div>

          <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="card-dark p-5">
              <Title level={4} style={{ color: '#ffffff', marginTop: 0 }}>
                接入示例
              </Title>
              <Paragraph style={{ color: '#94a3b8' }}>
                真实页面里直接在 `fraudAPI.detect()` 结果返回后调用 `buildFraudAlertPayload()`，
                再配合 `shouldShowFraudAlert()` 决定是否弹出。
              </Paragraph>
              <pre className="overflow-x-auto rounded-2xl border border-gray-700 bg-[#121425] p-4 text-sm text-slate-300">
                <code>{integrationExample}</code>
              </pre>
            </div>

            <div className="card-dark p-5">
              <Title level={4} style={{ color: '#ffffff', marginTop: 0 }}>
                交互说明
              </Title>
              <div className="space-y-3 text-sm text-slate-300">
                <div className="rounded-xl border border-gray-700 bg-[#18182d] p-3">
                  低风险样例保留轻量提示，帮助用户继续做信息核验。
                </div>
                <div className="rounded-xl border border-gray-700 bg-[#18182d] p-3">
                  中高风险样例会强调“暂停操作”“核验身份”“可信联系人联动”等动作。
                </div>
                <div className="rounded-xl border border-gray-700 bg-[#18182d] p-3">
                  按钮回调当前使用演示消息，后续可以直接接入报告页、通知流程和处置接口。
                </div>
              </div>
              <div className="mt-4">
                <Text style={{ color: '#64748b' }}>
                  当前页面路径：`/popup-demo`
                </Text>
              </div>
            </div>
          </div>
        </div>
      </Content>

      <FraudAlertModal
        open={modalOpen}
        alert={activeAlert}
        onClose={() => setModalOpen(false)}
        onAcknowledge={(alert) => {
          message.success(`已确认：${alert.title}`);
        }}
        onViewReport={(alert) => {
          message.info(`查看完整报告：${alert.scamType}`);
        }}
        onSeekHelp={() => {
          openOfficialPoliceHelpPage();
          message.warning('\u5df2\u6253\u5f00\u516c\u5b89\u90e8\u5b98\u65b9\u7f51\u7edc\u8fdd\u6cd5\u72af\u7f6a\u4e3e\u62a5\u9875\u9762\uff0c\u7d27\u6025\u60c5\u51b5\u8bf7\u76f4\u63a5\u62e8\u6253 110\u3002');
        }}
        onContactGuardian={(alert) => {
          message.warning(`测试占位：重点联系人联动 -> ${alert.scamType}`);
        }}
      />
    </Layout>
  );
}

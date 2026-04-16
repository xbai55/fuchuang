import { useState } from 'react';
import { AlertOutlined, ApiOutlined, ArrowLeftOutlined, EyeOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { Button, Layout, Space, Typography, message } from 'antd';
import { Link } from 'react-router-dom';
import FraudAlertModal from '../components/FraudAlertModal';
import { buildFraudAlertPayload, shouldShowFraudAlert } from '../utils/fraudPopup';
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
    label: '低风险示例',
    description: '正常提醒型弹窗，保留轻量提示和安全建议。',
    response: {
      risk_score: 26,
      risk_level: 'low',
      scam_type: '普通社交对话',
      warning_message:
        '当前内容未出现明显诈骗特征，但仍建议不要随意泄露验证码、银行卡号或身份证信息。',
      final_report: '# 低风险报告\n\n当前对话未触发高危规则，可继续观察。',
      guardian_alert: false,
    },
  },
  {
    key: 'medium',
    label: '中风险示例',
    description: '疑似诈骗预警，突出暂停操作和身份复核。',
    response: {
      risk_score: 68,
      risk_level: 'medium',
      scam_type: '兼职刷单诈骗',
      warning_message:
        '检测到**兼职返利**与**先垫付后返现**等典型话术。\n\n- 不要继续转账\n- 不要下载对方提供的 App\n- 尽快核实平台官方身份',
      final_report: '# 中风险报告\n\n建议立即复核对方身份，并保留聊天证据。',
      guardian_alert: false,
    },
  },
  {
    key: 'high',
    label: '高风险示例',
    description: '强提醒风格，附带监护人联动按钮和完整报告入口。',
    response: {
      risk_score: 92,
      risk_level: 'high',
      scam_type: '冒充客服退款诈骗',
      warning_message:
        '系统识别到**冒充客服退款**与**索要验证码**的高危组合，请立即停止操作。\n\n1. 不要提供短信验证码\n2. 不要点击陌生退款链接\n3. 立即联系官方客服核验',
      final_report:
        '# 高风险报告\n\n该内容与典型冒充电商客服诈骗高度相似，存在资金损失风险，建议立刻中断联系并通知监护人。',
      guardian_alert: true,
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
    <Layout className="min-h-screen bg-darker">
      <Content className="px-6 py-10">
        <div className="mx-auto max-w-6xl space-y-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="space-y-3">
              <Space size="middle" wrap>
                <span className="inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-4 py-1 text-sm text-indigo-300">
                  <ThunderboltOutlined />
                  独立弹窗演示页
                </span>
                <span className="inline-flex items-center gap-2 rounded-full border border-gray-700 bg-[#1b1d34] px-4 py-1 text-sm text-slate-300">
                  <ApiOutlined />
                  未接入正式检测链路
                </span>
              </Space>
              <Title level={1} style={{ color: '#ffffff', margin: 0 }}>
                反诈预警弹窗测试
              </Title>
              <Paragraph style={{ color: '#94a3b8', maxWidth: 760, marginBottom: 0 }}>
                这个页面只负责演示 UI 效果和未来接入方式。当前用三组模拟的
                `FraudDetectionResponse` 生成弹窗，不会影响现有聊天主流程。
              </Paragraph>
            </div>

            <Link to="/">
              <Button icon={<ArrowLeftOutlined />}>返回主页面</Button>
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
                    风险分数：{item.response.risk_score}
                    <br />
                    诈骗类型：{item.response.scam_type}
                    <br />
                    是否建议弹窗：{shouldPopup ? '是' : '否'}
                  </div>
                  <Button
                    type="primary"
                    icon={<EyeOutlined />}
                    className="btn-primary w-full"
                    onClick={() => openDemo(item.response)}
                  >
                    打开示例弹窗
                  </Button>
                </div>
              );
            })}
          </div>

          <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="card-dark p-5">
              <Title level={4} style={{ color: '#ffffff', marginTop: 0 }}>
                预留接口
              </Title>
              <Paragraph style={{ color: '#94a3b8' }}>
                后续正式接入时，直接把 `fraudAPI.detect()` 的返回结果传给
                `buildFraudAlertPayload()`，再用 `shouldShowFraudAlert()` 控制是否弹出即可。
              </Paragraph>
              <pre className="overflow-x-auto rounded-2xl border border-gray-700 bg-[#121425] p-4 text-sm text-slate-300">
                <code>{integrationExample}</code>
              </pre>
            </div>

            <div className="card-dark p-5">
              <Title level={4} style={{ color: '#ffffff', marginTop: 0 }}>
                演示说明
              </Title>
              <div className="space-y-3 text-sm text-slate-300">
                <div className="rounded-xl border border-gray-700 bg-[#18182d] p-3">
                  低风险样例默认不会强制要求弹窗，但这里保留了展示入口，方便比赛现场演示不同层级样式。
                </div>
                <div className="rounded-xl border border-gray-700 bg-[#18182d] p-3">
                  中高风险样例会强调“暂停操作”“核验身份”“联系监护人”等动作。
                </div>
                <div className="rounded-xl border border-gray-700 bg-[#18182d] p-3">
                  按钮回调目前只是测试占位，后续可以接报告页、监护人通知和上报接口。
                </div>
              </div>
              <div className="mt-4">
                <Text style={{ color: '#64748b' }}>
                  访问地址：`/popup-demo`
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
          message.info(`测试占位：查看报告 -> ${alert.scamType}`);
        }}
        onContactGuardian={(alert) => {
          message.warning(`测试占位：监护人联动 -> ${alert.scamType}`);
        }}
      />
    </Layout>
  );
}

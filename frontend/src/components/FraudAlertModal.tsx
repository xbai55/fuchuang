import { AlertOutlined, FileTextOutlined, PhoneOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import { Button, Divider, Modal, Progress, Tag, Typography } from 'antd';
import ReactMarkdown from 'react-markdown';
import type { FraudAlertPayload, RiskLevel } from '../types';

const { Paragraph, Text, Title } = Typography;

interface FraudAlertModalProps {
  open: boolean;
  alert: FraudAlertPayload | null;
  onClose: () => void;
  onAcknowledge?: (alert: FraudAlertPayload) => void;
  onViewReport?: (alert: FraudAlertPayload) => void;
  onContactGuardian?: (alert: FraudAlertPayload) => void;
}

const riskLevelConfig: Record<
  RiskLevel,
  {
    label: string;
    color: string;
    softColor: string;
    borderColor: string;
    title: string;
  }
> = {
  low: {
    label: '低风险',
    color: '#22c55e',
    softColor: 'rgba(34, 197, 94, 0.12)',
    borderColor: 'rgba(34, 197, 94, 0.32)',
    title: '风险较低，但仍建议保持警觉',
  },
  medium: {
    label: '中风险',
    color: '#f59e0b',
    softColor: 'rgba(245, 158, 11, 0.12)',
    borderColor: 'rgba(245, 158, 11, 0.32)',
    title: '检测到明显异常特征，建议暂停当前操作',
  },
  high: {
    label: '高风险',
    color: '#ef4444',
    softColor: 'rgba(239, 68, 68, 0.12)',
    borderColor: 'rgba(239, 68, 68, 0.32)',
    title: '系统判定为高危诈骗链路，请立即中止交互',
  },
};

export default function FraudAlertModal({
  open,
  alert,
  onClose,
  onAcknowledge,
  onViewReport,
  onContactGuardian,
}: FraudAlertModalProps) {
  if (!alert) {
    return null;
  }

  const config = riskLevelConfig[alert.riskLevel];

  return (
    <Modal
      open={open}
      onCancel={onClose}
      width={720}
      footer={[
        onViewReport && alert.finalReport ? (
          <Button
            key="report"
            icon={<FileTextOutlined />}
            onClick={() => onViewReport(alert)}
          >
            查看完整报告
          </Button>
        ) : null,
        alert.guardianAlert && onContactGuardian ? (
          <Button
            key="guardian"
            icon={<PhoneOutlined />}
            onClick={() => onContactGuardian(alert)}
          >
            联系监护人
          </Button>
        ) : null,
        <Button
          key="acknowledge"
          type="primary"
          danger={alert.riskLevel === 'high'}
          onClick={() => {
            onAcknowledge?.(alert);
            onClose();
          }}
        >
          我知道了
        </Button>,
      ]}
      title={null}
      destroyOnClose
    >
      <div className="space-y-5">
        <div
          className="rounded-2xl border p-5"
          style={{
            background: `linear-gradient(135deg, ${config.softColor} 0%, rgba(22, 24, 44, 0.96) 100%)`,
            borderColor: config.borderColor,
          }}
        >
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-2">
              <Tag
                bordered={false}
                icon={<AlertOutlined />}
                style={{
                  background: config.softColor,
                  color: config.color,
                  marginInlineEnd: 0,
                  paddingInline: 12,
                  height: 28,
                  lineHeight: '28px',
                  borderRadius: 999,
                }}
              >
                {config.label}预警
              </Tag>
              <Title level={3} style={{ color: '#ffffff', margin: 0 }}>
                {alert.title}
              </Title>
              <Paragraph style={{ color: '#cbd5e1', marginBottom: 0 }}>
                {config.title}
              </Paragraph>
            </div>
            <div className="min-w-[160px]">
              <Text style={{ color: '#94a3b8' }}>风险评分</Text>
              <Title level={2} style={{ color: config.color, margin: '4px 0 8px' }}>
                {alert.riskScore}
              </Title>
              <Progress
                percent={Math.max(0, Math.min(100, alert.riskScore))}
                showInfo={false}
                strokeColor={config.color}
                trailColor="rgba(148, 163, 184, 0.18)"
              />
            </div>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="card-dark p-4">
            <div className="flex items-center gap-2 mb-3 text-white">
              <SafetyCertificateOutlined style={{ color: config.color }} />
              <span className="font-medium">系统判断</span>
            </div>
            <Paragraph style={{ color: '#cbd5e1', marginBottom: 16 }}>
              {alert.summary}
            </Paragraph>
            <div className="flex flex-wrap gap-2">
              <Tag color={alert.riskLevel === 'high' ? 'red' : alert.riskLevel === 'medium' ? 'gold' : 'green'}>
                {alert.scamType || '待确认类型'}
              </Tag>
              {alert.guardianAlert && <Tag color="magenta">已触发监护人联动</Tag>}
            </div>
          </div>

          <div className="card-dark p-4">
            <div className="flex items-center gap-2 mb-3 text-white">
              <AlertOutlined style={{ color: config.color }} />
              <span className="font-medium">风险证据</span>
            </div>
            <div className="space-y-2">
              {alert.evidence.map((item) => (
                <div
                  key={item}
                  className="rounded-xl border border-gray-700 bg-[#18182d] px-3 py-2 text-sm text-slate-300"
                >
                  {item}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="card-dark p-4">
          <div className="flex items-center gap-2 mb-3 text-white">
            <PhoneOutlined style={{ color: config.color }} />
            <span className="font-medium">建议处置</span>
          </div>
          <div className="space-y-2">
            {alert.recommendations.map((item, index) => (
              <div
                key={`${item}-${index}`}
                className="rounded-xl border border-gray-700 bg-[#18182d] px-3 py-2 text-sm text-slate-300"
              >
                {index + 1}. {item}
              </div>
            ))}
          </div>
        </div>

        <Divider style={{ borderColor: 'rgba(148, 163, 184, 0.14)', margin: 0 }} />

        <div className="card-dark p-4">
          <div className="flex items-center gap-2 mb-3 text-white">
            <FileTextOutlined style={{ color: config.color }} />
            <span className="font-medium">预警文案</span>
          </div>
          <ReactMarkdown
            components={{
              p: ({ children }) => <p className="mb-2 last:mb-0 text-slate-300 leading-7">{children}</p>,
              ul: ({ children }) => <ul className="list-disc list-inside mb-2 text-slate-300">{children}</ul>,
              ol: ({ children }) => <ol className="list-decimal list-inside mb-2 text-slate-300">{children}</ol>,
              li: ({ children }) => <li className="mb-1">{children}</li>,
              strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
            }}
          >
            {alert.warningMessage}
          </ReactMarkdown>
        </div>
      </div>
    </Modal>
  );
}

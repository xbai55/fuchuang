import { AlertOutlined, FileTextOutlined, PhoneOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import { Button, Divider, Empty, Modal, Progress, Tag, Typography } from 'antd';
import ReactMarkdown from 'react-markdown';
import type { FraudAlertPayload, RiskLevel } from '../types';

const { Paragraph, Text, Title } = Typography;

interface FraudAlertModalProps {
  open: boolean;
  alert: FraudAlertPayload | null;
  onClose: () => void;
  onAcknowledge?: (alert: FraudAlertPayload) => void;
  onViewReport?: (alert: FraudAlertPayload) => void;
  onSeekHelp?: (alert: FraudAlertPayload) => void;
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
    label: '\u4f4e\u98ce\u9669',
    color: '#22c55e',
    softColor: 'rgba(34, 197, 94, 0.12)',
    borderColor: 'rgba(34, 197, 94, 0.32)',
    title: '\u5f53\u524d\u98ce\u9669\u8f83\u4f4e\uff0c\u4f46\u4ecd\u5efa\u8bae\u4fdd\u6301\u8b66\u60d5\u3002',
  },
  medium: {
    label: '\u4e2d\u98ce\u9669',
    color: '#f59e0b',
    softColor: 'rgba(245, 158, 11, 0.12)',
    borderColor: 'rgba(245, 158, 11, 0.32)',
    title: '\u68c0\u6d4b\u5230\u660e\u663e\u5f02\u5e38\u7279\u5f81\uff0c\u5efa\u8bae\u6682\u505c\u5f53\u524d\u64cd\u4f5c\u3002',
  },
  high: {
    label: '\u9ad8\u98ce\u9669',
    color: '#ef4444',
    softColor: 'rgba(239, 68, 68, 0.12)',
    borderColor: 'rgba(239, 68, 68, 0.32)',
    title: '\u7cfb\u7edf\u5224\u5b9a\u4e3a\u9ad8\u5371\u8bc8\u9a97\u94fe\u8def\uff0c\u8bf7\u7acb\u5373\u4e2d\u6b62\u4ea4\u4e92\u3002',
  },
};

export default function FraudAlertModal({
  open,
  alert,
  onClose,
  onAcknowledge,
  onViewReport,
  onSeekHelp,
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
      closable={alert.riskLevel !== 'high'}
      maskClosable={alert.riskLevel !== 'high'}
      keyboard={alert.riskLevel !== 'high'}
      width={720}
      footer={[
        onViewReport && alert.finalReport ? (
          <Button key="report" icon={<FileTextOutlined />} onClick={() => onViewReport(alert)}>
            {'\u67e5\u770b\u5b8c\u6574\u62a5\u544a'}
          </Button>
        ) : null,
        alert.riskLevel !== 'low' && onSeekHelp ? (
          <Button
            key="seek-help"
            icon={<SafetyCertificateOutlined />}
            danger={alert.riskLevel === 'high'}
            onClick={() => onSeekHelp(alert)}
          >
            {'\u4e00\u952e\u6c42\u52a9'}
          </Button>
        ) : null,
        alert.guardianAlert && onContactGuardian ? (
          <Button key="guardian" icon={<PhoneOutlined />} onClick={() => onContactGuardian(alert)}>
            {'\u8054\u7cfb\u91cd\u70b9\u8054\u7cfb\u4eba'}
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
          {'\u6211\u77e5\u9053\u4e86'}
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
                {`${config.label}\u9884\u8b66`}
              </Tag>
              <Title level={3} style={{ color: '#ffffff', margin: 0 }}>
                {alert.title}
              </Title>
              <Paragraph style={{ color: '#cbd5e1', marginBottom: 0 }}>
                {config.title}
              </Paragraph>
            </div>
            <div className="min-w-[160px]">
              <Text style={{ color: '#94a3b8' }}>{'\u98ce\u9669\u8bc4\u5206'}</Text>
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
            <div className="mb-3 flex items-center gap-2 text-white">
              <SafetyCertificateOutlined style={{ color: config.color }} />
              <span className="font-medium">{'\u7cfb\u7edf\u5224\u65ad'}</span>
            </div>
            <Paragraph style={{ color: '#cbd5e1', marginBottom: 16 }}>
              {alert.summary}
            </Paragraph>
            <div className="flex flex-wrap gap-2">
              <Tag color={alert.riskLevel === 'high' ? 'red' : alert.riskLevel === 'medium' ? 'gold' : 'green'}>
                {alert.scamType || '\u5f85\u786e\u8ba4\u7c7b\u578b'}
              </Tag>
              {alert.guardianAlert ? <Tag color="magenta">{'\u5df2\u89e6\u53d1\u91cd\u70b9\u8054\u7cfb\u4eba\u8054\u52a8'}</Tag> : null}
            </div>
          </div>

          <div className="card-dark p-4">
            <div className="mb-3 flex items-center gap-2 text-white">
              <AlertOutlined style={{ color: config.color }} />
              <span className="font-medium">{'\u98ce\u9669\u8bc1\u636e'}</span>
            </div>
            {alert.evidence.length > 0 ? (
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
            ) : (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={<span className="text-slate-400">{'\u6682\u65e0\u989d\u5916\u8bc1\u636e'}</span>}
              />
            )}
          </div>
        </div>

        <div className="card-dark p-4">
          <div className="mb-3 flex items-center gap-2 text-white">
            <PhoneOutlined style={{ color: config.color }} />
            <span className="font-medium">{'\u5efa\u8bae\u5904\u7f6e'}</span>
          </div>
          <div className="space-y-2">
            {alert.recommendations.map((item, index) => (
              <div
                key={`${item}-${index}`}
                className="rounded-xl border border-gray-700 bg-[#18182d] px-3 py-2 text-sm text-slate-300"
              >
                {`${index + 1}. ${item}`}
              </div>
            ))}
          </div>
        </div>

        <Divider style={{ borderColor: 'rgba(148, 163, 184, 0.14)', margin: 0 }} />

        <div className="card-dark p-4">
          <div className="mb-3 flex items-center gap-2 text-white">
            <FileTextOutlined style={{ color: config.color }} />
            <span className="font-medium">{'\u9884\u8b66\u6587\u6848'}</span>
          </div>
          <ReactMarkdown
            components={{
              p: ({ children }) => <p className="mb-2 last:mb-0 leading-7 text-slate-300">{children}</p>,
              ul: ({ children }) => <ul className="mb-2 list-inside list-disc text-slate-300">{children}</ul>,
              ol: ({ children }) => <ol className="mb-2 list-inside list-decimal text-slate-300">{children}</ol>,
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

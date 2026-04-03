import { useEffect, useRef, useState, type ReactNode } from 'react';
import { App, Button, Empty, Input, Layout, Popconfirm, Segmented, Spin, Tabs, Upload } from 'antd';
import { AudioOutlined, DeleteOutlined, PictureOutlined, SendOutlined, VideoCameraOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { agentAPI, fraudAPI } from '../services/api';
import { useI18n } from '../i18n';
import { maskText, USER_SETTINGS_CHANGED_EVENT } from '../utils/privacy';
import { storage } from '../utils/storage';
import type {
  AgentChatResponse,
  AgentTask,
  AgentTaskWsMessage,
  ChatHistory,
  FraudDetectionResponse,
  FraudEarlyWarning,
  FraudTask,
  FraudTaskWsMessage,
} from '../types';

const { Content } = Layout;
const { TextArea } = Input;

interface Message {
  type: 'user' | 'bot';
  content: string;
  streaming?: boolean;
  detailReport?: string;
  detailStreaming?: boolean;
  mode?: ChatMode;
  riskScore?: number;
  riskLevel?: 'low' | 'medium' | 'high';
  scamType?: string;
  guardianAlert?: boolean;
  suggestions?: string[];
}

type ChatMode = 'fraud' | 'agent';
type UploadMediaType = 'audio' | 'image' | 'video';

type ApiError = {
  response?: {
    data?: {
      detail?: string;
      message?: string;
    };
  };
};

export default function ChatPage() {
  const { message } = App.useApp();
  const { isZh } = useI18n();
  const [messages, setMessages] = useState<Message[]>([]);
  const [chatMode, setChatMode] = useState<ChatMode>('fraud');
  const [history, setHistory] = useState<ChatHistory[]>([]);
  const [selectedHistory, setSelectedHistory] = useState<ChatHistory | null>(null);
  const [deletingHistoryId, setDeletingHistoryId] = useState<number | null>(null);
  const [clearingHistory, setClearingHistory] = useState(false);
  const [agentConversationId, setAgentConversationId] = useState<string | null>(null);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [activeTab, setActiveTab] = useState('text');
  const [taskProgress, setTaskProgress] = useState<number | null>(null);
  const [privacyMode, setPrivacyMode] = useState<boolean>(() => storage.getUser()?.privacy_mode ?? false);
  const [inputDropActive, setInputDropActive] = useState(false);
  const [expandedDetailMap, setExpandedDetailMap] = useState<Record<string, boolean>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const taskSocketRef = useRef<WebSocket | null>(null);
  const streamMessageIndexRef = useRef<number | null>(null);
  const streamedDetailRef = useRef('');
  const agentStreamMessageIndexRef = useRef<number | null>(null);
  const streamedAgentContentRef = useRef('');
  const earlyWarningMessageKeyRef = useRef<string | null>(null);
  const inputDragDepthRef = useRef(0);

  const t = (zh: string, en: string) => (isZh ? zh : en);
  const isFraudMode = chatMode === 'fraud';

  const loadHistory = async () => {
    try {
      const historyData = await fraudAPI.getHistory();
      setHistory(historyData);
    } catch (error) {
      console.error(t('加载历史记录失败', 'Failed to load history'), error);
    }
  };

  useEffect(() => {
    void loadHistory();
  }, []);

  useEffect(() => {
    const syncPrivacy = () => {
      setPrivacyMode(storage.getUser()?.privacy_mode ?? false);
    };

    window.addEventListener('storage', syncPrivacy);
    window.addEventListener(USER_SETTINGS_CHANGED_EVENT, syncPrivacy);

    return () => {
      window.removeEventListener('storage', syncPrivacy);
      window.removeEventListener(USER_SETTINGS_CHANGED_EVENT, syncPrivacy);
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const getRiskBadgeClass = (level: string) => {
    switch (level) {
      case 'low':
        return 'badge-risk-low';
      case 'medium':
        return 'badge-risk-medium';
      case 'high':
        return 'badge-risk-high';
      default:
        return 'badge-risk-low';
    }
  };

  const getRiskBadgeText = (level: string) => {
    switch (level) {
      case 'low':
        return t('低风险', 'Low Risk');
      case 'medium':
        return t('中风险', 'Medium Risk');
      case 'high':
        return t('高风险', 'High Risk');
      default:
        return t('未知', 'Unknown');
    }
  };

  const normalizeRiskLevel = (level: string): 'low' | 'medium' | 'high' | undefined => {
    const normalized = (level || '').toLowerCase();
    if (normalized === 'low' || normalized === 'medium' || normalized === 'high') {
      return normalized;
    }
    return undefined;
  };

  const trimForContext = (content: string, maxLength: number = 500) => {
    if (!content || content.length <= maxLength) {
      return content;
    }
    return `${content.slice(0, maxLength)}...`;
  };

  const normalizeMarkdownContent = (rawContent: string) => {
    if (!rawContent) {
      return '';
    }

    let content = rawContent.replace(/\r\n/g, '\n').trim();
    content = content.replace(/<br\s*\/?>/gi, '  \n');

    // Some model responses are serialized with escaped line breaks.
    if (content.includes('\\n') && !content.includes('\n')) {
      content = content.replace(/\\n/g, '\n');
    }

    // Unwrap markdown code fences like ```markdown ... ``` so inner markdown can render.
    const fencedMarkdownMatch = content.match(/^```(?:markdown|md)?\s*([\s\S]*?)\s*```$/i);
    if (fencedMarkdownMatch?.[1]) {
      content = fencedMarkdownMatch[1].trim();
    }

    // Handle quoted markdown payloads: "## title\\n- item"
    if (content.length > 2 && ((content.startsWith('"') && content.endsWith('"')) || (content.startsWith("'") && content.endsWith("'")))) {
      const inner = content.slice(1, -1);
      if (inner.includes('\\n')) {
        content = inner.replace(/\\n/g, '\n').replace(/\\"/g, '"');
      }
    }

    return content;
  };

  const splitFraudSummaryAndDetail = (rawContent: string, fallbackDetail: string = '') => {
    const normalized = normalizeMarkdownContent(rawContent);
    const normalizedFallback = normalizeMarkdownContent(fallbackDetail);
    const detailMarkerPattern = /\n(?:##\s*)?(详细分析|Detailed Analysis)\s*\n/i;
    const markerMatch = detailMarkerPattern.exec(normalized);

    if (!markerMatch || markerMatch.index < 0) {
      return {
        summary: normalized,
        detail: normalizedFallback,
      };
    }

    const summary = normalized.slice(0, markerMatch.index).trim();
    const detail = normalized.slice(markerMatch.index + markerMatch[0].length).trim();

    return {
      summary: summary || normalized,
      detail: detail || normalizedFallback,
    };
  };

  const normalizeFraudWarning = (warningMessage: string, detailFallback: string = '') => {
    const split = splitFraudSummaryAndDetail(warningMessage, detailFallback);
    const summarySource = normalizeMarkdownContent(split.summary || warningMessage);
    const summaryCandidate = summarySource
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => {
        if (!line) {
          return false;
        }
        return !/^#{1,6}\s*(详细分析|Detailed Analysis)\s*$/i.test(line);
      })[0] ?? '';

    let summary = summaryCandidate || summarySource;
    if (summary.length > 180) {
      summary = `${summary.slice(0, 180).trim()}...`;
    }

    if (!summary) {
      summary = t(
        '系统正在持续核验，请查看详细报告了解完整分析。',
        'System is validating details. Open detailed report for full analysis.',
      );
    }

    let detail = normalizeMarkdownContent(split.detail || detailFallback);
    if (!detail && summarySource.length > 220) {
      detail = summarySource;
    }

    return {
      summary,
      detail,
    };
  };

  const getFraudActionItems = (level: 'low' | 'medium' | 'high') => {
    if (level === 'high') {
      return [
        t('立即停止转账或提供验证码', 'Stop transfer or sharing verification code immediately'),
        t('保留聊天、通话、转账截图并报警', 'Keep chat/call/transfer evidence and contact police'),
        t('第一时间联系银行冻结可疑交易', 'Contact your bank to freeze suspicious transactions as soon as possible'),
      ];
    }

    if (level === 'medium') {
      return [
        t('暂缓支付，先通过官方渠道核验身份', 'Pause payment and verify identity via official channels'),
        t('不要点击陌生链接，不安装远程控制软件', 'Do not click unknown links or install remote control apps'),
        t('如已泄露信息，尽快修改密码并开启二次验证', 'If data is leaked, change password and enable 2FA quickly'),
      ];
    }

    return [
      t('保持谨慎，继续核实关键信息来源', 'Stay cautious and keep verifying key information sources'),
      t('避免在陌生页面输入银行卡和验证码', 'Avoid entering bank card info and verification codes on unknown pages'),
      t('如对方催促操作，优先中断并咨询可信联系人', 'If urged to act quickly, stop and consult trusted contacts first'),
    ];
  };

  const formatFraudOutput = (response: FraudDetectionResponse, warningSummary?: string) => {
    const suspectedType = response.scam_type || t('未识别', 'Not identified');
    const warning = normalizeMarkdownContent(
      warningSummary || response.warning_message || t('暂无额外风险提醒。', 'No additional warning available.'),
    );
    const actionItems = getFraudActionItems(response.risk_level).map((item) => `- ${item}`).join('\n');

    return [
      `### ${t('风险结论', 'Risk Summary')}`,
      `- ${t('风险等级', 'Risk Level')}: **${getRiskBadgeText(response.risk_level)}**`,
      `- ${t('风险分数', 'Risk Score')}: **${response.risk_score}/100**`,
      `- ${t('疑似类型', 'Suspected Type')}: **${suspectedType}**`,
      `- ${t('监护预警', 'Guardian Alert')}: **${response.guardian_alert ? t('已触发', 'Triggered') : t('未触发', 'Not Triggered')}**`,
      '',
      `### ${t('关键提醒', 'Key Warning')}`,
      warning,
      '',
      `### ${t('建议处置', 'Recommended Actions')}`,
      actionItems,
    ].join('\n');
  };

  const getHistoryMode = (item: ChatHistory): ChatMode => {
    if (item.chat_mode === 'agent') {
      return 'agent';
    }
    if (item.scam_type === 'agent_chat') {
      return 'agent';
    }
    return 'fraud';
  };

  const appendAgentChunkMessage = (chunk: string) => {
    if (!chunk) {
      return;
    }

    streamedAgentContentRef.current = `${streamedAgentContentRef.current}${chunk}`;
    const latestContent = normalizeMarkdownContent(streamedAgentContentRef.current);

    setMessages((prev) => {
      const currentIndex = agentStreamMessageIndexRef.current;
      if (currentIndex === null || currentIndex < 0 || !prev[currentIndex]) {
        const createdIndex = prev.length;
        agentStreamMessageIndexRef.current = createdIndex;
        return [
          ...prev,
          {
            type: 'bot',
            mode: 'agent',
            content: latestContent,
            suggestions: [],
            streaming: true,
          },
        ];
      }

      const next = [...prev];
      next[currentIndex] = {
        ...next[currentIndex],
        content: latestContent,
        suggestions: [],
        streaming: true,
      };
      return next;
    });
  };

  const finalizeAgentStreamMessage = (response: AgentChatResponse) => {
    const streamedContent = normalizeMarkdownContent(streamedAgentContentRef.current || '');
    const finalContent = normalizeMarkdownContent(response.message || '') || streamedContent;

    const finalizedMessage: Message = {
      type: 'bot',
      mode: 'agent',
      content: finalContent,
      suggestions: response.suggestions ?? [],
      streaming: false,
    };

    setAgentConversationId(response.conversation_id);
    setMessages((prev) => {
      const currentIndex = agentStreamMessageIndexRef.current;
      const hasIndexedStreamingMessage =
        currentIndex !== null
        && currentIndex >= 0
        && Boolean(prev[currentIndex])
        && prev[currentIndex].mode === 'agent'
        && prev[currentIndex].streaming;

      let targetIndex = hasIndexedStreamingMessage ? currentIndex : null;

      if (targetIndex === null) {
        for (let i = prev.length - 1; i >= 0; i -= 1) {
          const candidate = prev[i];
          if (candidate.mode === 'agent' && candidate.streaming) {
            targetIndex = i;
            break;
          }
        }
      }

      if (targetIndex === null) {
        return [...prev, finalizedMessage];
      }

      const next = [...prev];
      next[targetIndex] = {
        ...next[targetIndex],
        ...finalizedMessage,
      };

      const cleaned = next.filter((item, idx) => {
        if (idx === targetIndex) {
          return true;
        }
        return !(item.mode === 'agent' && item.streaming);
      });

      return cleaned;
    });

    agentStreamMessageIndexRef.current = null;
    streamedAgentContentRef.current = '';
  };

  const loadHistoryConversation = (item: ChatHistory, notifyReady: boolean = false) => {
    const historyMode = getHistoryMode(item);

    resetStreamingState();
    setChatMode(historyMode);
    setAgentConversationId(null);
    setExpandedDetailMap({});
    setSelectedHistory(item);
    setInputText('');
    clearFiles();

    if (historyMode === 'agent') {
      setMessages([
        {
          type: 'user',
          mode: 'agent',
          content: item.user_message,
        },
        {
          type: 'bot',
          mode: 'agent',
          content: normalizeMarkdownContent(item.bot_response || ''),
          suggestions: [],
          streaming: false,
        },
      ]);

      if (notifyReady) {
        message.success(t('已载入历史对话，可继续发送消息', 'History loaded, you can continue the conversation'));
      }
      return;
    }

    const riskLevel = normalizeRiskLevel(item.risk_level);
    const historyRiskLevel: 'low' | 'medium' | 'high' = riskLevel ?? 'low';
    const normalizedHistory = normalizeFraudWarning(item.bot_response || '');
    const historyDetail = normalizedHistory.detail || normalizeMarkdownContent(item.bot_response || '');
    const historySummary = formatFraudOutput(
      {
        risk_score: item.risk_score,
        risk_level: historyRiskLevel,
        scam_type: item.scam_type || '',
        warning_message: normalizedHistory.summary,
        final_report: historyDetail,
        guardian_alert: item.guardian_alert,
      },
      normalizedHistory.summary,
    );

    setMessages([
      {
        type: 'user',
        mode: 'fraud',
        content: item.user_message,
      },
      {
        type: 'bot',
        mode: 'fraud',
        content: historySummary,
        detailReport: historyDetail || undefined,
        detailStreaming: false,
        riskScore: item.risk_score,
        riskLevel: historyRiskLevel,
        scamType: item.scam_type,
        guardianAlert: item.guardian_alert,
      },
    ]);

    if (notifyReady) {
      message.success(t('已载入历史对话，可继续发送消息', 'History loaded, you can continue the conversation'));
    }
  };

  const startNewConversation = () => {
    closeTaskSocket();
    resetStreamingState();
    setSelectedHistory(null);
    setAgentConversationId(null);
    setExpandedDetailMap({});
    setMessages([]);
    setInputText('');
    clearFiles();
  };

  const handleDeleteHistory = async (item: ChatHistory) => {
    setDeletingHistoryId(item.id);
    try {
      await fraudAPI.deleteHistory(item.id);
      setHistory((prev) => prev.filter((historyItem) => historyItem.id !== item.id));
      if (selectedHistory?.id === item.id) {
        startNewConversation();
      }
      message.success(t('历史记录已删除', 'History deleted'));
    } catch (error) {
      const apiError = error as ApiError;
      const errorMsg = apiError.response?.data?.detail ?? apiError.response?.data?.message ?? t('删除失败', 'Delete failed');
      message.error(errorMsg);
    } finally {
      setDeletingHistoryId(null);
    }
  };

  const handleClearHistory = async () => {
    setClearingHistory(true);
    try {
      const deletedCount = await fraudAPI.clearHistory();
      setHistory([]);
      if (selectedHistory) {
        startNewConversation();
      }
      message.success(isZh ? `已清空历史记录（${deletedCount} 条）` : `History cleared (${deletedCount})`);
    } catch (error) {
      const apiError = error as ApiError;
      const errorMsg = apiError.response?.data?.detail ?? apiError.response?.data?.message ?? t('清空失败', 'Clear failed');
      message.error(errorMsg);
    } finally {
      setClearingHistory(false);
    }
  };

  const handleModeChange = (value: string | number) => {
    const nextMode = value as ChatMode;
    closeTaskSocket();
    resetStreamingState();
    inputDragDepthRef.current = 0;
    setInputDropActive(false);
    setTaskProgress(null);
    setLoading(false);
    if (nextMode === 'agent') {
      clearFiles();
    }
    setChatMode(nextMode);
  };

  const buildDetectionMessage = (rawInput: string) => {
    const userInput = rawInput || t('请分析已上传的内容。', 'Please analyze the uploaded content.');
    if (!selectedHistory) {
      return userInput;
    }

    return [
      t('以下为历史对话上下文，请结合后再判断风险：', 'History conversation context, please consider it before risk judgment:'),
      `${t('历史用户输入', 'History user input')}: ${trimForContext(selectedHistory.user_message)}`,
      `${t('历史系统回复', 'History assistant reply')}: ${trimForContext(selectedHistory.bot_response)}`,
      `${t('当前用户输入', 'Current user input')}: ${userInput}`,
    ].join('\n');
  };

  const clearFiles = () => {
    setAudioFile(null);
    setImageFile(null);
    setVideoFile(null);
    setActiveTab('text');
  };

  const closeTaskSocket = () => {
    const socket = taskSocketRef.current;
    if (socket && socket.readyState !== WebSocket.CLOSING && socket.readyState !== WebSocket.CLOSED) {
      socket.close();
    }
    taskSocketRef.current = null;
  };

  const resetStreamingState = () => {
    streamMessageIndexRef.current = null;
    streamedDetailRef.current = '';
    agentStreamMessageIndexRef.current = null;
    streamedAgentContentRef.current = '';
  };

  const closeEarlyWarningPopup = () => {
    if (!earlyWarningMessageKeyRef.current) {
      return;
    }
    message.destroy(earlyWarningMessageKeyRef.current);
    earlyWarningMessageKeyRef.current = null;
  };

  const appendReportChunkMessage = (chunk: string) => {
    if (!chunk) {
      return;
    }

    streamedDetailRef.current = `${streamedDetailRef.current}${chunk}`;
    const latestDetail = normalizeMarkdownContent(streamedDetailRef.current);
    const latestContent = latestDetail || t('详细报告生成中，风险结论即将返回。', 'Detailed report is streaming, risk summary is coming soon.');

    setMessages((prev) => {
      const currentIndex = streamMessageIndexRef.current;
      if (currentIndex === null || currentIndex < 0 || !prev[currentIndex]) {
        const createdIndex = prev.length;
        streamMessageIndexRef.current = createdIndex;
        return [
          ...prev,
          {
            type: 'bot',
            mode: 'fraud',
            content: latestContent,
            detailReport: latestDetail,
            detailStreaming: true,
          },
        ];
      }

      const next = [...prev];
      next[currentIndex] = {
        ...next[currentIndex],
        content: latestContent,
        detailReport: latestDetail,
        detailStreaming: true,
      };
      return next;
    });
  };

  const finalizeFraudStreamMessage = (response: FraudDetectionResponse) => {
    const streamedDetail = normalizeMarkdownContent(streamedDetailRef.current || '');
    const responseDetail = normalizeMarkdownContent(response.final_report || '');
    const detailFallback = responseDetail || streamedDetail;
    const normalizedWarning = normalizeFraudWarning(response.warning_message || '', detailFallback);
    const finalDetail = normalizedWarning.detail || detailFallback;

    const finalizedMessage: Message = {
      type: 'bot',
      mode: 'fraud',
      content: formatFraudOutput(response, normalizedWarning.summary),
      detailReport: finalDetail || undefined,
      detailStreaming: false,
      riskScore: response.risk_score,
      riskLevel: response.risk_level,
      scamType: response.scam_type,
      guardianAlert: response.guardian_alert,
    };

    setMessages((prev) => {
      const currentIndex = streamMessageIndexRef.current;
      const hasIndexedStreamingMessage =
        currentIndex !== null
        && currentIndex >= 0
        && Boolean(prev[currentIndex])
        && prev[currentIndex].mode === 'fraud'
        && prev[currentIndex].detailStreaming;

      let targetIndex = hasIndexedStreamingMessage ? currentIndex : null;

      if (targetIndex === null) {
        for (let i = prev.length - 1; i >= 0; i -= 1) {
          const candidate = prev[i];
          if (candidate.mode === 'fraud' && candidate.detailStreaming) {
            targetIndex = i;
            break;
          }
        }
      }

      if (targetIndex === null) {
        return [...prev, finalizedMessage];
      }

      const next = [...prev];
      next[targetIndex] = {
        ...next[targetIndex],
        ...finalizedMessage,
      };

      // Remove stale streaming placeholders if any race created duplicates.
      const cleaned = next.filter((item, idx) => {
        if (idx === targetIndex) {
          return true;
        }
        return !(item.mode === 'fraud' && item.detailStreaming);
      });

      return cleaned;
    });

    resetStreamingState();
  };

  const resolveTaskResult = (task: FraudTask): FraudDetectionResponse | null => {
    if (!task.result) {
      return null;
    }

    const result = task.result as Partial<FraudDetectionResponse>;
    if (typeof result.risk_score !== 'number' || typeof result.risk_level !== 'string') {
      return null;
    }

    return {
      risk_score: result.risk_score,
      risk_level: result.risk_level as 'low' | 'medium' | 'high',
      scam_type: result.scam_type ?? '',
      warning_message: result.warning_message ?? '',
      final_report: result.final_report ?? '',
      guardian_alert: Boolean(result.guardian_alert),
    };
  };

  const resolveAgentTaskResult = (task: AgentTask): AgentChatResponse | null => {
    if (!task.result) {
      return null;
    }

    const result = task.result as Partial<AgentChatResponse>;
    if (typeof result.message !== 'string') {
      return null;
    }

    const suggestions = Array.isArray(result.suggestions) ? result.suggestions.filter((item): item is string => typeof item === 'string') : [];
    const toolCalls = Array.isArray(result.tool_calls) ? (result.tool_calls as Array<Record<string, unknown>>) : [];

    return {
      message: result.message,
      suggestions,
      tool_calls: toolCalls,
      conversation_id: result.conversation_id ?? agentConversationId ?? '',
    };
  };

  const waitForTaskByPolling = async (taskId: string): Promise<FraudDetectionResponse> => {
    const maxAttempts = 180;

    for (let i = 0; i < maxAttempts; i += 1) {
      const task = await fraudAPI.getTaskStatus(taskId);
      setTaskProgress(task.progress ?? 0);

      if (task.status === 'completed') {
        const result = resolveTaskResult(task);
        if (!result) {
          throw new Error(t('任务已完成，但未返回结果', 'Task completed but no result was returned'));
        }
        return result;
      }

      if (task.status === 'failed' || task.status === 'timeout') {
        throw new Error(task.error || t('分析任务失败', 'Analysis task failed'));
      }

      await new Promise((resolve) => {
        setTimeout(resolve, 1000);
      });
    }

    throw new Error(t('任务等待超时，请稍后重试', 'Task timed out. Please try again later'));
  };

  const waitForAgentTaskByPolling = async (taskId: string): Promise<AgentChatResponse> => {
    const maxAttempts = 180;

    for (let i = 0; i < maxAttempts; i += 1) {
      const task = await agentAPI.getTaskStatus(taskId);

      if (task.status === 'completed') {
        const result = resolveAgentTaskResult(task);
        if (!result) {
          throw new Error(t('任务已完成，但未返回结果', 'Task completed but no result was returned'));
        }
        return result;
      }

      if (task.status === 'failed' || task.status === 'timeout') {
        throw new Error(task.error || t('助理任务失败', 'Assistant task failed'));
      }

      await new Promise((resolve) => {
        setTimeout(resolve, 1000);
      });
    }

    throw new Error(t('任务等待超时，请稍后重试', 'Task timed out. Please try again later'));
  };

  const waitForTaskByWebSocket = (
    taskId: string,
    options?: { onReportChunk?: (chunk: string) => void },
  ): Promise<FraudDetectionResponse> => {
    return new Promise((resolve, reject) => {
      let settled = false;
      let socket: WebSocket;

      try {
        socket = fraudAPI.createTaskSocket(taskId);
      } catch {
        reject(new Error(t('无法建立实时连接', 'Unable to establish realtime connection')));
        return;
      }

      taskSocketRef.current = socket;

      const cleanup = () => {
        settled = true;
        if (taskSocketRef.current === socket) {
          taskSocketRef.current = null;
        }
        if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
          socket.close();
        }
      };

      socket.onmessage = (event) => {
        let payload: FraudTaskWsMessage;
        try {
          payload = JSON.parse(event.data) as FraudTaskWsMessage;
        } catch {
          return;
        }

        if (payload.task && typeof payload.task.progress === 'number') {
          setTaskProgress(payload.task.progress);
        }

        if (payload.event === 'report_chunk') {
          if (payload.chunk) {
            options?.onReportChunk?.(payload.chunk);
          }
          return;
        }

        if (payload.event === 'task_completed') {
          const resultFromEvent = payload.result;
          const resultFromTask = payload.task ? resolveTaskResult(payload.task) : null;
          const finalResult = resultFromEvent ?? resultFromTask;

          if (!finalResult) {
            cleanup();
            reject(new Error(t('任务完成但结果解析失败', 'Task completed but result parsing failed')));
            return;
          }

          cleanup();
          resolve(finalResult);
          return;
        }

        if (payload.event === 'task_failed' || payload.event === 'error') {
          cleanup();
          reject(new Error(payload.error || payload.message || t('实时任务执行失败', 'Realtime task failed')));
        }
      };

      socket.onerror = () => {
        if (settled) {
          return;
        }
        cleanup();
        reject(new Error(t('实时连接异常', 'Realtime connection error')));
      };

      socket.onclose = () => {
        if (settled) {
          return;
        }
        cleanup();
        reject(new Error(t('实时连接已断开', 'Realtime connection closed')));
      };
    });
  };

  const waitForAgentTaskByWebSocket = (
    taskId: string,
    options?: { onAgentChunk?: (chunk: string) => void },
  ): Promise<AgentChatResponse> => {
    return new Promise((resolve, reject) => {
      let settled = false;
      let socket: WebSocket;

      try {
        socket = agentAPI.createTaskSocket(taskId);
      } catch {
        reject(new Error(t('无法建立实时连接', 'Unable to establish realtime connection')));
        return;
      }

      taskSocketRef.current = socket;

      const cleanup = () => {
        settled = true;
        if (taskSocketRef.current === socket) {
          taskSocketRef.current = null;
        }
        if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
          socket.close();
        }
      };

      socket.onmessage = (event) => {
        let payload: AgentTaskWsMessage;
        try {
          payload = JSON.parse(event.data) as AgentTaskWsMessage;
        } catch {
          return;
        }

        if (payload.event === 'agent_chunk') {
          if (payload.chunk) {
            options?.onAgentChunk?.(payload.chunk);
          }
          return;
        }

        if (payload.event === 'task_completed') {
          const resultFromEvent = payload.result;
          const resultFromTask = payload.task ? resolveAgentTaskResult(payload.task) : null;
          const finalResult = resultFromEvent ?? resultFromTask;

          if (!finalResult) {
            cleanup();
            reject(new Error(t('任务完成但结果解析失败', 'Task completed but result parsing failed')));
            return;
          }

          cleanup();
          resolve(finalResult);
          return;
        }

        if (payload.event === 'task_failed' || payload.event === 'error') {
          cleanup();
          reject(new Error(payload.error || payload.message || t('实时任务执行失败', 'Realtime task failed')));
        }
      };

      socket.onerror = () => {
        if (settled) {
          return;
        }
        cleanup();
        reject(new Error(t('实时连接异常', 'Realtime connection error')));
      };

      socket.onclose = () => {
        if (settled) {
          return;
        }
        cleanup();
        reject(new Error(t('实时连接已断开', 'Realtime connection closed')));
      };
    });
  };

  const showEarlyWarningPopup = (earlyWarning?: FraudEarlyWarning | null) => {
    if (!earlyWarning?.warning_message) {
      return;
    }

    closeEarlyWarningPopup();

    const clueText = earlyWarning.risk_clues && earlyWarning.risk_clues.length > 0
      ? ` ${t('线索', 'Clues')}: ${earlyWarning.risk_clues.slice(0, 2).join('；')}`
      : '';

    const content = `${t('快速预警', 'Early Warning')}: ${earlyWarning.warning_message}${clueText}`;
    const popupType = earlyWarning.risk_level === 'low' ? 'info' : 'warning';
    const popupKey = `fraud-early-warning-${Date.now()}`;
    earlyWarningMessageKeyRef.current = popupKey;

    message.open({
      key: popupKey,
      type: popupType,
      content,
      duration: 0,
    });
  };

  const handleSend = async () => {
    if (isFraudMode && !inputText.trim() && !audioFile && !imageFile && !videoFile) {
      message.warning(t('请先输入内容或上传文件', 'Please enter text or upload a file first'));
      return;
    }

    if (!isFraudMode && !inputText.trim()) {
      message.warning(t('请输入要发送给智能助理的内容', 'Please enter a message for the assistant'));
      return;
    }

    if (!isFraudMode && (audioFile || imageFile || videoFile)) {
      message.warning(t('智能助理模式仅支持文本，请切回反诈模式上传文件', 'Assistant mode supports text only. Switch to fraud mode for file analysis'));
      return;
    }

    const userMessage = inputText.trim();
    const attachedKinds: string[] = [];
    if (isFraudMode) {
      if (audioFile) attachedKinds.push(t('[音频]', '[Audio]'));
      if (imageFile) attachedKinds.push(t('[图片]', '[Image]'));
      if (videoFile) attachedKinds.push(t('[视频]', '[Video]'));
    }

    const displayMessage = [userMessage, attachedKinds.join(' ')].filter(Boolean).join(' ');
    const detectionMessage = buildDetectionMessage(userMessage);

    closeTaskSocket();
    resetStreamingState();
    closeEarlyWarningPopup();
    setMessages((prev) => [...prev, { type: 'user', mode: chatMode, content: displayMessage }]);
    setInputText('');
    setLoading(true);
    setTaskProgress(isFraudMode ? 0 : null);

    try {
      if (isFraudMode) {
        const task = await fraudAPI.detectAsync({
          message: detectionMessage,
          audio_file: audioFile ?? undefined,
          image_file: imageFile ?? undefined,
          video_file: videoFile ?? undefined,
        });

        showEarlyWarningPopup(
          task.early_warning ?? {
            risk_score: 0,
            risk_level: 'low',
            warning_message: t(
              '已启动快速预警，正在生成完整分析结果。',
              'Fast early warning started. Full analysis is in progress.',
            ),
            source: 'frontend_fallback',
            is_preliminary: true,
          },
        );

        let response: FraudDetectionResponse;
        try {
          response = await waitForTaskByWebSocket(task.task_id, {
            onReportChunk: appendReportChunkMessage,
          });
        } catch (wsError) {
          console.warn(t('实时推送失败，降级为轮询', 'Realtime push failed, fallback to polling'), wsError);
          response = await waitForTaskByPolling(task.task_id);
        }

        finalizeFraudStreamMessage(response);
        closeEarlyWarningPopup();

        if (response.guardian_alert) {
          message.warning(t('该结果已触发监护预警', 'Guardian alert has been triggered'));
        }

        clearFiles();
        await loadHistory();
      } else {
        const task = await agentAPI.chatAsync({
          message: userMessage,
          conversation_id: agentConversationId ?? undefined,
          context: selectedHistory
            ? {
                resumed_history_id: selectedHistory.id,
                resumed_history_time: selectedHistory.created_at,
              }
            : undefined,
        });

        let response: AgentChatResponse;
        try {
          response = await waitForAgentTaskByWebSocket(task.task_id, {
            onAgentChunk: appendAgentChunkMessage,
          });
        } catch (wsError) {
          console.warn(t('实时推送失败，降级为轮询', 'Realtime push failed, fallback to polling'), wsError);
          response = await waitForAgentTaskByPolling(task.task_id);
        }

        finalizeAgentStreamMessage(response);
        await loadHistory();
      }
    } catch (error) {
      closeEarlyWarningPopup();
      const apiError = error as ApiError;
      const errorMsg =
        apiError.response?.data?.detail ??
        apiError.response?.data?.message ??
        (isFraudMode ? t('识别失败', 'Analysis failed') : t('发送失败', 'Send failed'));
      message.error(errorMsg);
    } finally {
      closeTaskSocket();
      setLoading(false);
      setTaskProgress(null);
    }
  };

  useEffect(() => {
    return () => {
      closeTaskSocket();
      resetStreamingState();
      closeEarlyWarningPopup();
    };
  }, []);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void handleSend();
    }
  };

  const getFileExtension = (filename: string) => {
    const dotIndex = filename.lastIndexOf('.');
    if (dotIndex < 0) {
      return '';
    }
    return filename.slice(dotIndex).toLowerCase();
  };

  const beforeUpload = (file: File, fileType: UploadMediaType) => {
    const validMimeTypes: Record<UploadMediaType, string[]> = {
      audio: ['audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/mp3', 'audio/mp4', 'audio/x-m4a'],
      image: ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
      video: ['video/mp4', 'video/quicktime', 'video/x-msvideo'],
    };

    const validExtensions: Record<UploadMediaType, string[]> = {
      audio: ['.mp3', '.wav', '.m4a'],
      image: ['.jpg', '.jpeg', '.png', '.gif', '.webp'],
      video: ['.mp4', '.mov', '.avi'],
    };

    const maxSize = {
      audio: 10 * 1024 * 1024,
      image: 5 * 1024 * 1024,
      video: 50 * 1024 * 1024,
    };

    const fileTypeLabels: Record<UploadMediaType, string> = {
      audio: t('音频', 'audio'),
      image: t('图片', 'image'),
      video: t('视频', 'video'),
    };

    const normalizedMime = (file.type || '').toLowerCase();
    const extension = getFileExtension(file.name || '');
    const mimeMatched = normalizedMime ? validMimeTypes[fileType].includes(normalizedMime) : false;
    const extensionMatched = extension ? validExtensions[fileType].includes(extension) : false;

    if (!mimeMatched && !extensionMatched) {
      message.error(t(`不支持该${fileTypeLabels[fileType]}文件格式`, `Unsupported ${fileTypeLabels[fileType]} format`));
      return Upload.LIST_IGNORE;
    }

    if (file.size > maxSize[fileType]) {
      message.error(t(`${fileTypeLabels[fileType]}文件过大`, `${fileTypeLabels[fileType]} file is too large`));
      return Upload.LIST_IGNORE;
    }

    if (fileType === 'audio') setAudioFile(file);
    if (fileType === 'image') setImageFile(file);
    if (fileType === 'video') setVideoFile(file);
    return false;
  };

  const resolveDroppedFileType = (file: File): UploadMediaType | null => {
    const normalizedMime = (file.type || '').toLowerCase();
    if (normalizedMime.startsWith('audio/')) {
      return 'audio';
    }
    if (normalizedMime.startsWith('image/')) {
      return 'image';
    }
    if (normalizedMime.startsWith('video/')) {
      return 'video';
    }

    const extension = getFileExtension(file.name || '');
    if (['.mp3', '.wav', '.m4a'].includes(extension)) {
      return 'audio';
    }
    if (['.jpg', '.jpeg', '.png', '.gif', '.webp'].includes(extension)) {
      return 'image';
    }
    if (['.mp4', '.mov', '.avi'].includes(extension)) {
      return 'video';
    }

    return null;
  };

  const resetInputDropState = () => {
    inputDragDepthRef.current = 0;
    setInputDropActive(false);
  };

  const handleDroppedFiles = (files: Iterable<File>) => {
    const droppedList = Array.from(files || []);
    if (droppedList.length === 0) {
      return;
    }

    if (!isFraudMode) {
      message.warning(t('智能助理模式不支持上传文件，请切换到反诈分析模式。', 'Assistant mode does not support file upload. Switch to fraud analysis mode.'));
      return;
    }

    if (loading) {
      message.warning(t('当前任务处理中，请稍后再上传文件。', 'A task is in progress. Please upload files later.'));
      return;
    }

    const firstFilesByType: Partial<Record<UploadMediaType, File>> = {};
    let unsupportedCount = 0;
    let duplicateCount = 0;

    for (const file of droppedList) {
      const fileType = resolveDroppedFileType(file);
      if (!fileType) {
        unsupportedCount += 1;
        continue;
      }
      if (firstFilesByType[fileType]) {
        duplicateCount += 1;
        continue;
      }
      firstFilesByType[fileType] = file;
    }

    const fileTypes = Object.keys(firstFilesByType) as UploadMediaType[];
    if (fileTypes.length === 0) {
      message.warning(t('未识别到可上传的音频、图片或视频文件。', 'No supported audio, image, or video file was recognized.'));
      return;
    }

    let firstAcceptedTab: string | null = null;
    for (const fileType of fileTypes) {
      const droppedFile = firstFilesByType[fileType];
      if (!droppedFile) {
        continue;
      }
      const result = beforeUpload(droppedFile, fileType);
      if (result !== Upload.LIST_IGNORE && !firstAcceptedTab) {
        firstAcceptedTab = fileType;
      }
    }

    if (firstAcceptedTab) {
      setActiveTab(firstAcceptedTab);
    }

    if (duplicateCount > 0) {
      message.info(t('同类型文件仅保留第一个，其余已忽略。', 'Only the first file of each type is kept; others were ignored.'));
    }
    if (unsupportedCount > 0) {
      message.warning(t('部分文件类型不支持，已自动忽略。', 'Some files are unsupported and were ignored.'));
    }
  };

  const hasTextPayloadInDataTransfer = (dataTransfer: DataTransfer | null | undefined) => {
    if (!dataTransfer) {
      return false;
    }
    const typeSet = new Set(Array.from(dataTransfer.types || []));
    return typeSet.has('text/plain') || typeSet.has('text/uri-list') || typeSet.has('text/html');
  };

  const hasAnyFilesInDataTransfer = (dataTransfer: DataTransfer | null | undefined) => {
    if (!dataTransfer) {
      return false;
    }

    if (dataTransfer.files && dataTransfer.files.length > 0) {
      return true;
    }

    if (dataTransfer.items && dataTransfer.items.length > 0) {
      return Array.from(dataTransfer.items).some((item) => item.kind === 'file');
    }

    const typeSet = new Set(Array.from(dataTransfer.types || []));
    return typeSet.has('Files') || typeSet.has('application/x-moz-file') || typeSet.has('public.file-url');
  };

  const hasAnyDroppablePayload = (dataTransfer: DataTransfer | null | undefined) => {
    if (!dataTransfer) {
      return false;
    }
    if (hasAnyFilesInDataTransfer(dataTransfer) || hasTextPayloadInDataTransfer(dataTransfer)) {
      return true;
    }
    return Array.from(dataTransfer.types || []).length > 0;
  };

  const extractUrlsFromTextPayload = (raw: string) => {
    if (!raw) {
      return [] as string[];
    }

    const urls: string[] = [];

    const uriLines = raw
      .split(/\r?\n/g)
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith('#'));
    for (const line of uriLines) {
      if (/^https?:\/\//i.test(line)) {
        urls.push(line);
      }
    }

    const urlMatches = raw.match(/https?:\/\/[^\s"'<>]+/gi) || [];
    urls.push(...urlMatches);

    return Array.from(new Set(urls));
  };

  const collectDropStringPayloads = (dataTransfer: DataTransfer) => {
    const payloads = new Set<string>();
    const preferredTypes = ['DownloadURL', 'text/uri-list', 'text/plain', 'text/html', 'text/x-moz-url'];

    for (const type of preferredTypes) {
      const value = dataTransfer.getData(type);
      if (value) {
        payloads.add(value);
      }
    }

    for (const type of Array.from(dataTransfer.types || [])) {
      if (!type || type.toLowerCase() === 'files') {
        continue;
      }
      const value = dataTransfer.getData(type);
      if (value) {
        payloads.add(value);
      }
    }

    return Array.from(payloads);
  };

  const getExtensionByMimeType = (mimeType: string) => {
    const normalized = (mimeType || '').toLowerCase();
    const mapping: Record<string, string> = {
      'image/jpeg': '.jpg',
      'image/png': '.png',
      'image/gif': '.gif',
      'image/webp': '.webp',
      'audio/mpeg': '.mp3',
      'audio/mp3': '.mp3',
      'audio/wav': '.wav',
      'audio/x-wav': '.wav',
      'audio/mp4': '.m4a',
      'audio/x-m4a': '.m4a',
      'video/mp4': '.mp4',
      'video/quicktime': '.mov',
      'video/x-msvideo': '.avi',
    };
    return mapping[normalized] || '';
  };

  const buildFilenameFromUrl = (url: string, mimeType: string, index: number) => {
    try {
      const parsed = new URL(url);
      const pathname = decodeURIComponent(parsed.pathname || '');
      const candidate = pathname.split('/').pop() || '';
      if (candidate && candidate.includes('.')) {
        return candidate;
      }
    } catch {
      // Ignore URL parsing failure and fallback to generated name.
    }

    const ext = getExtensionByMimeType(mimeType) || '.bin';
    return `dropped_${Date.now()}_${index}${ext}`;
  };

  const extractUrlsFromDownloadUrlPayload = (raw: string) => {
    const normalized = (raw || '').trim();
    if (!normalized) {
      return [] as string[];
    }

    // Chrome/Chromium DownloadURL format: <mime>:<filename>:<url>
    const match = normalized.match(/^[^:]+:[^:]+:(https?:\/\/.+)$/i);
    if (match?.[1]) {
      return [match[1]];
    }

    return [] as string[];
  };

  const tryCreateFileFromUrl = async (url: string, index: number): Promise<File | null> => {
    if (!/^https?:\/\//i.test(url)) {
      return null;
    }

    try {
      const response = await fetch(url, { method: 'GET' });
      if (!response.ok) {
        return null;
      }

      const blob = await response.blob();
      if (!blob || blob.size <= 0) {
        return null;
      }

      const filename = buildFilenameFromUrl(url, blob.type, index);
      const file = new File([blob], filename, { type: blob.type || 'application/octet-stream' });
      return resolveDroppedFileType(file) ? file : null;
    } catch {
      return null;
    }
  };

  const collectDropFiles = (dataTransfer: DataTransfer) => {
    const fileMap = new Map<string, File>();

    const insertFile = (file: File | null) => {
      if (!file) {
        return;
      }
      const key = `${file.name}|${file.size}|${file.type}|${file.lastModified}`;
      if (!fileMap.has(key)) {
        fileMap.set(key, file);
      }
    };

    for (const file of Array.from(dataTransfer.files || [])) {
      insertFile(file);
    }

    if (dataTransfer.items && dataTransfer.items.length > 0) {
      for (const item of Array.from(dataTransfer.items)) {
        if (item.kind !== 'file') {
          continue;
        }
        insertFile(item.getAsFile());
      }
    }

    return Array.from(fileMap.values());
  };

  const handleDroppedPayload = async (
    directFiles: File[],
    stringPayloads: string[],
  ) => {
    if (directFiles.length > 0) {
      handleDroppedFiles(directFiles);
      return;
    }

    const downloadUrlCandidates = stringPayloads.flatMap((payload) => extractUrlsFromDownloadUrlPayload(payload));
    const urlCandidates = Array.from(
      new Set([
        ...downloadUrlCandidates,
        ...stringPayloads.flatMap((payload) => extractUrlsFromTextPayload(payload)),
      ]),
    );

    if (urlCandidates.length === 0) {
      if (stringPayloads.length > 0) {
        message.warning(
          t(
            '已检测到飞书拖拽内容，但未解析出可下载文件链接。请先下载到本地再拖入。',
            'Feishu drag payload was detected, but no downloadable file link was parsed. Please save locally first.',
          ),
        );
        return;
      }
      message.warning(
        t(
          '当前拖拽内容不是本地文件，无法直接上传。请先在飞书中下载到本地后再拖入。',
          'The dropped content is not a local file. Please download it from Feishu first, then drag it in.',
        ),
      );
      return;
    }

    const convertedFiles: File[] = [];
    for (const [index, url] of urlCandidates.slice(0, 3).entries()) {
      const file = await tryCreateFileFromUrl(url, index + 1);
      if (file) {
        convertedFiles.push(file);
      }
    }

    if (convertedFiles.length > 0) {
      handleDroppedFiles(convertedFiles);
      return;
    }

    message.warning(
      t(
        '检测到飞书链接，但浏览器无法直接读取该资源。请先另存到本地后拖入。',
        'Detected Feishu links, but the browser cannot access them directly. Please save locally and drag again.',
      ),
    );
  };

  const handleInputDragEnter = (event: React.DragEvent<HTMLElement>) => {
    if (!hasAnyDroppablePayload(event.dataTransfer)) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    inputDragDepthRef.current += 1;
    setInputDropActive(true);
  };

  const handleInputDragOver = (event: React.DragEvent<HTMLElement>) => {
    if (!hasAnyDroppablePayload(event.dataTransfer)) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    event.dataTransfer.dropEffect = 'copy';
    if (!inputDropActive) {
      setInputDropActive(true);
    }
  };

  const handleInputDragLeave = (event: React.DragEvent<HTMLElement>) => {
    if (!hasAnyDroppablePayload(event.dataTransfer)) {
      return;
    }
    const nextTarget = event.relatedTarget as Node | null;
    if (nextTarget && event.currentTarget.contains(nextTarget)) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    inputDragDepthRef.current = 0;
    setInputDropActive(false);
  };

  const handleInputDrop = (event: React.DragEvent<HTMLElement>) => {
    event.preventDefault();
    event.stopPropagation();
    const droppedData = event.dataTransfer;
    resetInputDropState();
    if (!droppedData) {
      return;
    }
    const directFiles = collectDropFiles(droppedData);
    const stringPayloads = collectDropStringPayloads(droppedData);
    void handleDroppedPayload(directFiles, stringPayloads);
  };

  useEffect(() => {
    const onWindowDragOver = (event: DragEvent) => {
      if (event.defaultPrevented) {
        return;
      }
      if (!hasAnyDroppablePayload(event.dataTransfer)) {
        return;
      }
      event.preventDefault();
      if (event.dataTransfer) {
        event.dataTransfer.dropEffect = 'copy';
      }
    };

    const onWindowDrop = (event: DragEvent) => {
      if (event.defaultPrevented) {
        return;
      }
      if (!hasAnyDroppablePayload(event.dataTransfer)) {
        return;
      }

      event.preventDefault();
      resetInputDropState();
      if (!event.dataTransfer) {
        return;
      }
      const directFiles = collectDropFiles(event.dataTransfer);
      const stringPayloads = collectDropStringPayloads(event.dataTransfer);
      void handleDroppedPayload(directFiles, stringPayloads);
    };

    const onWindowDragLeave = (event: DragEvent) => {
      if (!event.relatedTarget) {
        resetInputDropState();
      }
    };

    window.addEventListener('dragover', onWindowDragOver);
    window.addEventListener('drop', onWindowDrop);
    window.addEventListener('dragleave', onWindowDragLeave);

    return () => {
      window.removeEventListener('dragover', onWindowDragOver);
      window.removeEventListener('drop', onWindowDrop);
      window.removeEventListener('dragleave', onWindowDragLeave);
    };
  }, [isFraudMode, loading]);

  const markdownComponents = {
    h2: ({ children }: { children?: ReactNode }) => <h2 className="mb-1 mt-2 text-base font-semibold text-white first:mt-0">{children}</h2>,
    h3: ({ children }: { children?: ReactNode }) => <h3 className="mb-1 mt-2 text-sm font-semibold text-gray-100 first:mt-0">{children}</h3>,
    p: ({ children }: { children?: ReactNode }) => <p className="mb-1 last:mb-0">{children}</p>,
    ul: ({ children }: { children?: ReactNode }) => <ul className="mb-1 list-disc list-inside">{children}</ul>,
    ol: ({ children }: { children?: ReactNode }) => <ol className="mb-1 list-decimal list-inside">{children}</ol>,
    li: ({ children }: { children?: ReactNode }) => <li className="mb-0.5">{children}</li>,
    pre: ({ children }: { children?: ReactNode }) => <pre className="mb-1 max-w-full overflow-x-auto rounded-lg bg-black/30 p-2">{children}</pre>,
    code: ({ children }: { children?: ReactNode }) => <code className="rounded bg-black/30 px-1 py-0.5 text-[13px] break-all whitespace-pre-wrap">{children}</code>,
    table: ({ children }: { children?: ReactNode }) => (
      <div className="mb-1 max-w-full overflow-x-auto">
        <table className="min-w-full border-collapse text-xs">{children}</table>
      </div>
    ),
    thead: ({ children }: { children?: ReactNode }) => <thead className="bg-white/5">{children}</thead>,
    tbody: ({ children }: { children?: ReactNode }) => <tbody>{children}</tbody>,
    tr: ({ children }: { children?: ReactNode }) => <tr className="border border-white/10">{children}</tr>,
    th: ({ children }: { children?: ReactNode }) => <th className="border border-white/10 px-2 py-1 text-left font-semibold">{children}</th>,
    td: ({ children }: { children?: ReactNode }) => <td className="border border-white/10 px-2 py-1 align-top">{children}</td>,
    a: ({ href, children }: { href?: string; children?: ReactNode }) => (
      <a href={href} target="_blank" rel="noreferrer" className="break-all text-blue-300 underline hover:text-blue-200">
        {children}
      </a>
    ),
    blockquote: ({ children }: { children?: ReactNode }) => <blockquote className="mb-1 border-l-2 border-gray-600 pl-3 text-gray-300">{children}</blockquote>,
  };

  return (
    <Layout className="bg-darker min-h-screen">
      <Content className="ml-[260px] p-6">
        <div className="mx-auto flex h-[calc(100vh-48px)] max-w-5xl gap-6">
          <div className="flex min-w-0 flex-1 flex-col">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-white">
                  {isFraudMode ? t('风险识别对话', 'Risk Analysis Chat') : t('智能助理对话', 'Agent Chat')}
                </h1>
                <p className="mt-1 text-sm text-gray-400">
                  {isFraudMode
                    ? t('粘贴可疑内容或上传媒体文件进行分析。', 'Paste suspicious content or upload media for analysis.')
                    : t('与智能助理直接对话，获取防骗建议与解释。', 'Chat with the assistant for anti-scam guidance and explanations.')}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Segmented
                  value={chatMode}
                  onChange={handleModeChange}
                  disabled={loading}
                  options={[
                    { label: t('反诈分析', 'Fraud Analysis'), value: 'fraud' },
                    { label: t('智能助理', 'Agent Chat'), value: 'agent' },
                  ]}
                />
                {selectedHistory ? (
                  <span className="rounded-full border border-amber-400/50 bg-amber-500/10 px-3 py-1 text-xs text-amber-100">
                    {isFraudMode
                      ? `${t('历史会话模式', 'History Mode')} #${selectedHistory.id}`
                      : t('已读取历史记录', 'History Loaded')}
                  </span>
                ) : null}
                <Button onClick={startNewConversation} disabled={loading}>
                  {t('新对话', 'New Chat')}
                </Button>
              </div>
            </div>

            <div className="card-dark mb-4 flex-1 overflow-y-auto p-4">
              {messages.length === 0 && !loading ? (
                <div className="flex h-full items-center justify-center">
                  <Empty
                    description={
                      <span className="text-gray-400">
                        {isFraudMode
                          ? t('开始对话后，分析结果会显示在这里', 'Analysis results will appear here after you start a chat')
                          : t('开始提问后，助理回复会显示在这里', 'Assistant replies will appear here after you send a question')}
                      </span>
                    }
                  />
                </div>
              ) : (
                <div className="space-y-4">
                  {selectedHistory && isFraudMode ? (
                    <div className="rounded-lg border border-amber-400/30 bg-amber-500/10 p-3">
                      <div className="text-xs font-medium text-amber-100">
                        {t('当前正在基于历史记录继续对话', 'You are continuing from a historical conversation')}
                      </div>
                      <div className="mt-1 text-xs text-amber-200/90">
                        {t('记录时间', 'Record time')}: {selectedHistory.created_at}
                      </div>
                    </div>
                  ) : null}
                  {selectedHistory && !isFraudMode ? (
                    <div className="rounded-lg border border-sky-400/30 bg-sky-500/10 p-3">
                      <div className="text-xs font-medium text-sky-100">
                        {t('已载入历史记录，切换模式不会改动历史数据', 'History loaded, mode switching will not modify stored records')}
                      </div>
                    </div>
                  ) : null}
                  {messages.map((msg, index) => {
                    const detailKey = `detail-${index}`;
                    const detailExpanded = msg.detailStreaming || Boolean(expandedDetailMap[detailKey]);

                    return (
                    <div key={`${msg.type}-${index}`} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div
                        className={`min-w-0 max-w-[80%] break-words ${msg.type === 'user' ? 'message-user' : 'message-bot'} ${
                          msg.type === 'bot' && msg.mode === 'fraud' ? 'fraud-message-box' : ''
                        }`}
                      >
                        {msg.type === 'bot' ? (
                          <>
                            {msg.riskScore !== undefined ? (
                              <div className="mb-1 flex items-center gap-2">
                                <span className={getRiskBadgeClass(msg.riskLevel ?? 'low')}>
                                  {getRiskBadgeText(msg.riskLevel ?? 'low')} ({msg.riskScore}/100)
                                </span>
                                {msg.scamType ? <span className="text-xs text-gray-400">{msg.scamType}</span> : null}
                              </div>
                            ) : null}
                            <div className="mb-1 text-[11px] uppercase tracking-wide text-gray-500">
                              {msg.mode === 'agent' ? t('智能助理', 'Agent Chat') : t('反诈分析', 'Fraud Analysis')}
                            </div>
                            <div className="chat-markdown-body">
                              <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                                components={markdownComponents}
                              >
                                {normalizeMarkdownContent(msg.content)}
                              </ReactMarkdown>
                            </div>
                            {msg.mode === 'agent' && msg.streaming ? (
                              <div className="mt-2 flex items-center gap-2 text-xs text-sky-300">
                                <Spin size="small" />
                                <span>{t('正在流式生成回复...', 'Streaming response...')}</span>
                              </div>
                            ) : null}
                            {msg.mode === 'fraud' && (msg.detailReport || msg.detailStreaming) ? (
                              <div className="mt-1">
                                <Button
                                  size="small"
                                  onClick={() => {
                                    setExpandedDetailMap((prev) => ({
                                      ...prev,
                                      [detailKey]: !prev[detailKey],
                                    }));
                                  }}
                                >
                                  {msg.detailStreaming
                                    ? t('详细报告生成中...', 'Detailed report is streaming...')
                                    : detailExpanded
                                      ? t('收起详细报告', 'Hide Detailed Report')
                                      : t('查看详细报告', 'Show Detailed Report')}
                                </Button>
                              </div>
                            ) : null}
                            {msg.mode === 'fraud' && (msg.detailReport || msg.detailStreaming) && detailExpanded ? (
                              <div className="mt-2 rounded-lg border border-gray-600/40 bg-black/15 p-3">
                                <div className="mb-1 text-[11px] uppercase tracking-wide text-gray-400">
                                  {t('详细报告', 'Detailed Report')}
                                </div>
                                {msg.detailStreaming ? (
                                  <div className="mb-2 flex items-center gap-2 text-xs text-amber-300">
                                    <Spin size="small" />
                                    <span>{t('正在流式输出详细报告...', 'Streaming detailed report...')}</span>
                                  </div>
                                ) : null}
                                <div className="chat-markdown-body">
                                  <ReactMarkdown
                                    remarkPlugins={[remarkGfm]}
                                    components={markdownComponents}
                                  >
                                    {normalizeMarkdownContent(msg.detailReport || '')}
                                  </ReactMarkdown>
                                </div>
                              </div>
                            ) : null}
                            {msg.mode === 'agent' && msg.suggestions && msg.suggestions.length > 0 ? (
                              <div className="mt-2 flex flex-wrap gap-2">
                                {msg.suggestions.slice(0, 3).map((suggestion, suggestionIndex) => (
                                  <Button
                                    key={`${index}-suggestion-${suggestionIndex}`}
                                    size="small"
                                    onClick={() => setInputText(suggestion)}
                                    disabled={loading}
                                  >
                                    {suggestion}
                                  </Button>
                                ))}
                              </div>
                            ) : null}
                            {msg.guardianAlert ? (
                              <div className="mt-2 rounded-lg border border-red-500/30 bg-red-500/10 p-2 text-sm text-red-400">
                                {t('已触发监护预警', 'Guardian alert triggered')}
                              </div>
                            ) : null}
                          </>
                        ) : (
                          <p className="mb-0 whitespace-pre-wrap break-all">{privacyMode ? maskText(msg.content) : msg.content}</p>
                        )}
                      </div>
                    </div>
                    );
                  })}
                  {loading ? (
                    <div className="flex justify-start">
                      <div className="message-bot">
                        <Spin size="small" />
                        <span className="ml-2 text-gray-400">
                          {isFraudMode
                            ? taskProgress !== null
                              ? t(`分析中（${taskProgress}%）`, `Analyzing (${taskProgress}%)`)
                              : t('分析中...', 'Analyzing...')
                            : t('助理思考中...', 'Assistant is thinking...')}
                        </span>
                      </div>
                    </div>
                  ) : null}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            <div
              className={`card-dark p-4 transition-all duration-150 ${inputDropActive ? 'ring-2 ring-cyan-400/70 ring-offset-0' : ''}`}
              onDragEnter={handleInputDragEnter}
              onDragOver={handleInputDragOver}
              onDragLeave={handleInputDragLeave}
              onDrop={handleInputDrop}
            >
              {inputDropActive ? (
                <div className="mb-3 rounded-lg border border-cyan-300/50 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-100">
                  {isFraudMode
                    ? t('松开即可添加文件，可同时拖入音频、图片、视频（每类仅保留首个）。', 'Drop to attach files. You can drag audio, image, and video together (first file per type).')
                    : t('当前模式仅支持文本输入，若需上传文件请切换到反诈分析。', 'Current mode supports text only. Switch to fraud analysis to upload files.')}
                </div>
              ) : null}
              <Tabs
                activeKey={activeTab}
                onChange={setActiveTab}
                items={[
                  {
                    key: 'text',
                    label: t('文本', 'Text'),
                    children: (
                      <div
                        onDragEnter={handleInputDragEnter}
                        onDragOver={handleInputDragOver}
                        onDragLeave={handleInputDragLeave}
                        onDrop={handleInputDrop}
                      >
                        <TextArea
                          value={inputText}
                          onChange={(event) => setInputText(event.target.value)}
                          onKeyDown={handleKeyDown}
                          placeholder={
                            isFraudMode
                              ? t('请描述发生了什么，或粘贴可疑消息内容。', 'Describe what happened, or paste suspicious messages.')
                              : t('请输入你想咨询的问题，例如“这条短信可信吗？”', 'Ask anything, such as "Is this message trustworthy?"')
                          }
                          autoSize={{ minRows: 3, maxRows: 6 }}
                          className="bg-dark-lighter border-gray-700 text-white"
                          disabled={loading}
                        />
                      </div>
                    ),
                  },
                  {
                    key: 'audio',
                    label: t('音频', 'Audio'),
                    icon: <AudioOutlined />,
                    disabled: !isFraudMode,
                    children: (
                      <Upload.Dragger beforeUpload={(file) => beforeUpload(file, 'audio')} maxCount={1} showUploadList={false}>
                        <p className="ant-upload-drag-icon">
                          <AudioOutlined className="text-blue-500" />
                        </p>
                        <p className="ant-upload-text">{t('将音频文件拖到此处，或点击选择', 'Drag audio here, or click to upload')}</p>
                        <p className="ant-upload-hint">{t('支持格式：MP3、WAV、M4A，最大 10 MB', 'Formats: MP3, WAV, M4A. Max 10 MB')}</p>
                      </Upload.Dragger>
                    ),
                  },
                  {
                    key: 'image',
                    label: t('图片', 'Image'),
                    icon: <PictureOutlined />,
                    disabled: !isFraudMode,
                    children: (
                      <Upload.Dragger beforeUpload={(file) => beforeUpload(file, 'image')} maxCount={1} showUploadList={false}>
                        <p className="ant-upload-drag-icon">
                          <PictureOutlined className="text-green-500" />
                        </p>
                        <p className="ant-upload-text">{t('将图片拖到此处，或点击选择', 'Drag image here, or click to upload')}</p>
                        <p className="ant-upload-hint">{t('支持格式：JPG、PNG、GIF、WEBP，最大 5 MB', 'Formats: JPG, PNG, GIF, WEBP. Max 5 MB')}</p>
                      </Upload.Dragger>
                    ),
                  },
                  {
                    key: 'video',
                    label: t('视频', 'Video'),
                    icon: <VideoCameraOutlined />,
                    disabled: !isFraudMode,
                    children: (
                      <Upload.Dragger beforeUpload={(file) => beforeUpload(file, 'video')} maxCount={1} showUploadList={false}>
                        <p className="ant-upload-drag-icon">
                          <VideoCameraOutlined className="text-purple-500" />
                        </p>
                        <p className="ant-upload-text">{t('将视频拖到此处，或点击选择', 'Drag video here, or click to upload')}</p>
                        <p className="ant-upload-hint">{t('支持格式：MP4、MOV、AVI，最大 50 MB', 'Formats: MP4, MOV, AVI. Max 50 MB')}</p>
                      </Upload.Dragger>
                    ),
                  },
                ]}
              />

              <div className="mt-3 flex items-center justify-between">
                <div className="text-sm text-gray-400">
                  {isFraudMode ? (
                    <>
                      {audioFile ? <span className="mr-3">{t('音频', 'Audio')}: {audioFile.name}</span> : null}
                      {imageFile ? <span className="mr-3">{t('图片', 'Image')}: {imageFile.name}</span> : null}
                      {videoFile ? <span className="mr-3">{t('视频', 'Video')}: {videoFile.name}</span> : null}
                    </>
                  ) : (
                    <span>{t('智能助理模式仅支持文本输入', 'Assistant mode only supports text input')}</span>
                  )}
                </div>
                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  onClick={() => void handleSend()}
                  loading={loading}
                  disabled={isFraudMode ? (!inputText.trim() && !audioFile && !imageFile && !videoFile) : !inputText.trim()}
                  className="btn-primary"
                >
                  {isFraudMode ? t('开始分析', 'Analyze') : t('发送给助理', 'Send to Assistant')}
                </Button>
              </div>
            </div>
          </div>

          <div className="hidden h-full w-80 shrink-0 lg:block">
            <div className="card-dark flex h-full flex-col overflow-hidden p-4">
              <div className="mb-4 flex shrink-0 items-center justify-between gap-2">
                <h2 className="text-lg font-semibold text-white">{t('最近记录', 'Recent Records')}</h2>
                <Popconfirm
                  title={t('确定清空全部历史记录吗？', 'Clear all history records?')}
                  description={t('该操作不可撤销', 'This action cannot be undone')}
                  okText={t('清空', 'Clear')}
                  cancelText={t('取消', 'Cancel')}
                  onConfirm={() => void handleClearHistory()}
                >
                  <Button
                    size="small"
                    danger
                    loading={clearingHistory}
                    disabled={loading || history.length === 0 || deletingHistoryId !== null}
                  >
                    {t('清空', 'Clear')}
                  </Button>
                </Popconfirm>
              </div>
              {history.length === 0 ? (
                <div className="flex min-h-0 flex-1 items-center justify-center">
                  <Empty description={<span className="text-gray-400">{t('暂无历史记录', 'No history yet')}</span>} />
                </div>
              ) : (
                <div className="min-h-0 flex-1 overflow-y-auto pr-1">
                  <div className="space-y-3 pb-1">
                    {history.map((item) => {
                      const historyMode = getHistoryMode(item);
                      return (
                        <div
                          key={item.id}
                          className={`rounded-lg border bg-dark-lighter p-3 ${
                            selectedHistory?.id === item.id ? 'border-primary/80' : 'border-gray-800'
                          }`}
                        >
                          <div className="mb-1 text-xs uppercase tracking-wide text-gray-500">
                            {historyMode === 'agent'
                              ? t('智能助理', 'Agent Chat')
                              : `${getRiskBadgeText(item.risk_level)} (${item.risk_score}/100)`}
                          </div>
                          <div className="text-xs text-gray-300">
                            {t('用户', 'User')}: {privacyMode ? maskText(item.user_message) : item.user_message}
                          </div>
                          <div className="mt-1 line-clamp-2 break-all text-xs text-gray-400">
                            {t('系统', 'Assistant')}: {privacyMode ? maskText(item.bot_response) : item.bot_response}
                          </div>
                          <div className="mt-2 text-xs text-gray-500">{item.created_at}</div>
                          <div className="mt-3 flex items-center gap-2">
                            <Button
                              size="small"
                              onClick={() => loadHistoryConversation(item)}
                              disabled={loading || clearingHistory || deletingHistoryId !== null}
                            >
                              {t('读取', 'Read')}
                            </Button>
                            <Button
                              size="small"
                              type="primary"
                              onClick={() => loadHistoryConversation(item, true)}
                              disabled={loading || clearingHistory || deletingHistoryId !== null}
                            >
                              {t('继续对话', 'Resume')}
                            </Button>
                            <Popconfirm
                              title={t('确定删除该条记录吗？', 'Delete this record?')}
                              okText={t('删除', 'Delete')}
                              cancelText={t('取消', 'Cancel')}
                              onConfirm={() => void handleDeleteHistory(item)}
                            >
                              <Button
                                size="small"
                                danger
                                icon={<DeleteOutlined />}
                                loading={deletingHistoryId === item.id}
                                disabled={loading || clearingHistory}
                              >
                                {t('删除', 'Delete')}
                              </Button>
                            </Popconfirm>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </Content>
    </Layout>
  );
}

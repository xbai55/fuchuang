import { useState, useRef, useEffect } from 'react';
import { Layout, Input, Button, message, Empty, Spin } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import { fraudAPI } from '../services/api';
import { storage } from '../utils/storage';
import type { FraudDetectionResponse, ChatHistory } from '../types';

const { Content } = Layout;
const { TextArea } = Input;

interface Message {
  type: 'user' | 'bot';
  content: string;
  riskScore?: number;
  riskLevel?: 'low' | 'medium' | 'high';
  scamType?: string;
  guardianAlert?: boolean;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<ChatHistory[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<any>(null);

  // 加载历史记录
  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    try {
      const historyData = await fraudAPI.getHistory();
      setHistory(historyData);
    } catch (error) {
      console.error('Failed to load history:', error);
    }
  };

  // 自动滚动到底部
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
        return '低风险';
      case 'medium':
        return '中风险';
      case 'high':
        return '高风险';
      default:
        return '未知';
    }
  };

  const handleSend = async () => {
    if (!inputText.trim()) return;

    const userMessage = inputText.trim();
    setInputText('');
    
    // 添加用户消息
    setMessages(prev => [...prev, { type: 'user', content: userMessage }]);
    setLoading(true);

    try {
      const response = await fraudAPI.detect({ message: userMessage });
      
      // 添加机器人回复
      setMessages(prev => [...prev, {
        type: 'bot',
        content: response.warning_message,
        riskScore: response.risk_score,
        riskLevel: response.risk_level,
        scamType: response.scam_type,
        guardianAlert: response.guardian_alert
      }]);

      // 如果需要通知监护人，显示提示
      if (response.guardian_alert) {
        message.warning('系统已自动通知您的监护人！');
      }

      // 重新加载历史记录
      loadHistory();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '检测失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <Layout className="bg-darker min-h-screen">
      <Content className="ml-[260px] p-6">
        <div className="max-w-4xl mx-auto h-[calc(100vh-48px)] flex flex-col">
          {/* 聊天区域 */}
          <div className="flex-1 overflow-y-auto mb-4 p-4 card-dark">
            {messages.length === 0 && !loading ? (
              <div className="h-full flex items-center justify-center">
                <Empty
                  description={
                    <div>
                      <div className="text-xl font-medium mb-2 text-white">
                        欢迎使用反诈预警系统
                      </div>
                      <div className="text-gray-400">
                        输入对话内容，AI 将为您实时分析诈骗风险
                      </div>
                    </div>
                  }
                  image={null}
                />
              </div>
            ) : (
              <div className="space-y-4">
                {messages.map((msg, index) => (
                  <div
                    key={index}
                    className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div className={`max-w-[80%] ${msg.type === 'user' ? 'message-user' : 'message-bot'}`}>
                      {msg.type === 'bot' && (
                        <>
                          {/* 风险等级徽章 */}
                          {msg.riskScore !== undefined && (
                            <div className="mb-2 flex items-center gap-2">
                              <span className={getRiskBadgeClass(msg.riskLevel || 'low')}>
                                {getRiskBadgeText(msg.riskLevel || 'low')} ({msg.riskScore}/100)
                              </span>
                              {msg.scamType && (
                                <span className="text-xs text-gray-400">
                                  {msg.scamType}
                                </span>
                              )}
                            </div>
                          )}
                          <ReactMarkdown
                            components={{
                              p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                              ul: ({ children }) => <ul className="list-disc list-inside mb-2">{children}</ul>,
                              ol: ({ children }) => <ol className="list-decimal list-inside mb-2">{children}</ol>,
                              li: ({ children }) => <li className="mb-1">{children}</li>,
                              strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                            }}
                          >
                            {msg.content}
                          </ReactMarkdown>
                          {msg.guardianAlert && (
                            <div className="mt-2 p-2 bg-red-500/10 border border-red-500/30 rounded-lg">
                              <span className="text-red-400 text-sm">
                                ⚠️ 已自动通知监护人
                              </span>
                            </div>
                          )}
                        </>
                      )}
                      {msg.type === 'user' && (
                        <p className="mb-0">{msg.content}</p>
                      )}
                    </div>
                  </div>
                ))}
                {loading && (
                  <div className="flex justify-start">
                    <div className="message-bot">
                      <Spin size="small" />
                      <span className="ml-2 text-gray-400">正在分析...</span>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* 输入区域 */}
          <div className="p-4 card-dark">
            <TextArea
              ref={inputRef}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入对话内容，AI 将为您分析诈骗风险...（Enter 发送，Shift+Enter 换行）"
              autoSize={{ minRows: 2, maxRows: 6 }}
              className="bg-dark-lighter border-gray-700 text-white"
              disabled={loading}
            />
            <div className="mt-3 flex justify-end">
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSend}
                loading={loading}
                disabled={!inputText.trim()}
                className="btn-primary"
              >
                发送
              </Button>
            </div>
          </div>
        </div>
      </Content>
    </Layout>
  );
}

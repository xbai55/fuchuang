import { useState, useRef, useEffect } from 'react';
import { Layout, Input, Button, App, Empty, Spin, Upload, Tabs } from 'antd';
import { SendOutlined, AudioOutlined, PictureOutlined, VideoCameraOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import { fraudAPI } from '../services/api';
import type { ChatHistory } from '../types';

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
  const { message } = App.useApp();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [, setHistory] = useState<ChatHistory[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<any>(null);
  
  // 多模态文件上传状态
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [activeTab, setActiveTab] = useState('text');

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
    if (!inputText.trim() && !audioFile && !imageFile && !videoFile) {
      message.warning('请输入文本或上传文件');
      return;
    }

    const userMessage = inputText.trim();
    const hasFiles = audioFile || imageFile || videoFile;
    
    // 构建用户消息显示
    let displayMessage = userMessage;
    if (hasFiles) {
      const fileTypes: string[] = [];
      if (audioFile) fileTypes.push('[语音]');
      if (imageFile) fileTypes.push('[图片]');
      if (videoFile) fileTypes.push('[视频]');
      displayMessage = userMessage ? `${userMessage} ${fileTypes.join(' ')}` : fileTypes.join(' ');
    }
    
    setInputText('');
    
    // 添加用户消息
    setMessages(prev => [...prev, { type: 'user', content: displayMessage }]);
    setLoading(true);

    try {
      const response = await fraudAPI.detect({ 
        message: userMessage || '分析上传的文件',
        audio_file: audioFile || undefined,
        image_file: imageFile || undefined,
        video_file: videoFile || undefined
      });
      
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

      // 清除文件
      setAudioFile(null);
      setImageFile(null);
      setVideoFile(null);
      setActiveTab('text');

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

  // 文件上传配置
  const uploadProps = {
    maxCount: 1,
    beforeUpload: (file: File, fileType: 'audio' | 'image' | 'video') => {
      // 验证文件类型
      const validTypes = {
        audio: ['audio/mpeg', 'audio/wav', 'audio/mp3', 'audio/mp4'],
        image: ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
        video: ['video/mp4', 'video/quicktime', 'video/x-msvideo']
      };
      
      if (!validTypes[fileType].includes(file.type)) {
        message.error(`请上传正确的${fileType === 'audio' ? '音频' : fileType === 'image' ? '图片' : '视频'}格式`);
        return false;
      }
      
      // 验证文件大小（音频 10MB，图片 5MB，视频 50MB）
      const maxSize = {
        audio: 10 * 1024 * 1024,
        image: 5 * 1024 * 1024,
        video: 50 * 1024 * 1024
      };
      
      if (file.size > maxSize[fileType]) {
        message.error(`文件大小不能超过${maxSize[fileType] / 1024 / 1024}MB`);
        return false;
      }
      
      // 设置文件
      if (fileType === 'audio') setAudioFile(file);
      else if (fileType === 'image') setImageFile(file);
      else if (fileType === 'video') setVideoFile(file);
      
      return false; // 阻止自动上传
    },
    onRemove: () => {
      setAudioFile(null);
      setImageFile(null);
      setVideoFile(null);
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
                        支持文本、语音、图片、视频多模态诈骗检测
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
            {/* 多模态输入选项卡 */}
            <Tabs
              activeKey={activeTab}
              onChange={setActiveTab}
              items={[
                {
                  key: 'text',
                  label: '文本输入',
                  children: (
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
                  )
                },
                {
                  key: 'audio',
                  label: '语音上传',
                  icon: <AudioOutlined />,
                  children: (
                    <div className="p-4 bg-dark-lighter rounded-lg border border-gray-700">
                      {audioFile ? (
                        <div className="flex items-center justify-between">
                          <span className="text-white">{audioFile.name}</span>
                          <Button onClick={() => setAudioFile(null)}>移除</Button>
                        </div>
                      ) : (
                        <Upload.Dragger {...uploadProps} beforeUpload={(f) => uploadProps.beforeUpload(f, 'audio')}>
                          <p className="ant-upload-drag-icon">
                            <AudioOutlined className="text-blue-500" />
                          </p>
                          <p className="ant-upload-text">点击或拖拽音频文件到此处</p>
                          <p className="ant-upload-hint">支持 MP3、WAV、M4A 格式，最大 10MB</p>
                        </Upload.Dragger>
                      )}
                    </div>
                  )
                },
                {
                  key: 'image',
                  label: '图片上传',
                  icon: <PictureOutlined />,
                  children: (
                    <div className="p-4 bg-dark-lighter rounded-lg border border-gray-700">
                      {imageFile ? (
                        <div className="flex items-center justify-between">
                          <span className="text-white">{imageFile.name}</span>
                          <Button onClick={() => setImageFile(null)}>移除</Button>
                        </div>
                      ) : (
                        <Upload.Dragger {...uploadProps} beforeUpload={(f) => uploadProps.beforeUpload(f, 'image')}>
                          <p className="ant-upload-drag-icon">
                            <PictureOutlined className="text-green-500" />
                          </p>
                          <p className="ant-upload-text">点击或拖拽图片文件到此处</p>
                          <p className="ant-upload-hint">支持 JPG、PNG、GIF、WEBP 格式，最大 5MB</p>
                        </Upload.Dragger>
                      )}
                    </div>
                  )
                },
                {
                  key: 'video',
                  label: '视频上传',
                  icon: <VideoCameraOutlined />,
                  children: (
                    <div className="p-4 bg-dark-lighter rounded-lg border border-gray-700">
                      {videoFile ? (
                        <div className="flex items-center justify-between">
                          <span className="text-white">{videoFile.name}</span>
                          <Button onClick={() => setVideoFile(null)}>移除</Button>
                        </div>
                      ) : (
                        <Upload.Dragger {...uploadProps} beforeUpload={(f) => uploadProps.beforeUpload(f, 'video')}>
                          <p className="ant-upload-drag-icon">
                            <VideoCameraOutlined className="text-purple-500" />
                          </p>
                          <p className="ant-upload-text">点击或拖拽视频文件到此处</p>
                          <p className="ant-upload-hint">支持 MP4、MOV、AVI 格式，最大 50MB</p>
                        </Upload.Dragger>
                      )}
                    </div>
                  )
                }
              ]}
            />
            
            <div className="mt-3 flex justify-between items-center">
              <div className="text-sm text-gray-400">
                {audioFile && <span className="mr-2">📎 语音：{audioFile.name}</span>}
                {imageFile && <span className="mr-2">📎 图片：{imageFile.name}</span>}
                {videoFile && <span className="mr-2">📎 视频：{videoFile.name}</span>}
              </div>
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSend}
                loading={loading}
                disabled={(!inputText.trim() && !audioFile && !imageFile && !videoFile)}
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

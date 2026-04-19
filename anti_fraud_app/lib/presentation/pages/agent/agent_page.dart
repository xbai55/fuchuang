import 'package:flutter/material.dart';

import '../../../data/api/agent_api.dart';
import '../../theme/app_theme.dart';
import '../../widgets/markdown_text.dart';

/// 反诈助手页面（Agent 对话）
class AgentPage extends StatefulWidget {
  final String? initialUserMessage;
  final String? initialAssistantMessage;

  const AgentPage({
    super.key,
    this.initialUserMessage,
    this.initialAssistantMessage,
  });

  @override
  State<AgentPage> createState() => _AgentPageState();
}

class _AgentPageState extends State<AgentPage> {
  final AgentApi _agentApi = AgentApi();
  final TextEditingController _messageController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final List<_AgentMessage> _messages = [];
  final List<String> _suggestions = const [
    '对方让我先转保证金，这正常吗？',
    '陌生客服说账户异常，要我下载软件。',
    '收到可疑链接或二维码，帮我判断一下。',
  ];

  bool _isSending = false;
  String? _conversationId;

  @override
  void initState() {
    super.initState();
    if ((widget.initialUserMessage ?? '').trim().isNotEmpty) {
      _messages.add(_AgentMessage.user(widget.initialUserMessage!.trim()));
    }
    if ((widget.initialAssistantMessage ?? '').trim().isNotEmpty) {
      _messages.add(
        _AgentMessage.assistant(widget.initialAssistantMessage!.trim()),
      );
    }
  }

  @override
  void dispose() {
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.backgroundColor,
      appBar: AppBar(
        title: const Text('反诈助手'),
        actions: [
          IconButton(
            tooltip: '新建聊天',
            icon: const Icon(Icons.add_comment_outlined),
            onPressed: _startNewChat,
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(child: _buildContent()),
            _buildInputArea(),
          ],
        ),
      ),
    );
  }

  Widget _buildContent() {
    if (_messages.isEmpty && !_isSending) {
      return ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _buildHeroCard(),
          const SizedBox(height: 18),
          ..._suggestions.map(
            (suggestion) => _SuggestionTile(
              icon: _suggestionIcon(suggestion),
              title: suggestion,
              subtitle: _suggestionSubtitle(suggestion),
              onTap: () => _sendMessage(suggestion),
            ),
          ),
        ],
      );
    }

    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 20),
      itemCount: _messages.length + (_isSending ? 1 : 0),
      itemBuilder: (context, index) {
        if (index == _messages.length) {
          return _buildTypingBubble();
        }
        return _buildMessageBubble(_messages[index]);
      },
    );
  }

  Widget _buildHeroCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: AppTheme.primaryGradient,
        borderRadius: BorderRadius.circular(8),
      ),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.support_agent_rounded,
            color: Color(0xFF04201C),
            size: 36,
          ),
          SizedBox(height: 18),
          Text(
            '有疑问，先问清楚',
            style: TextStyle(
              color: Color(0xFF04201C),
              fontSize: 24,
              fontWeight: FontWeight.w900,
            ),
          ),
          SizedBox(height: 8),
          Text(
            '把对方的话术、链接、收款要求或身份说法发来，我会帮你拆解风险。',
            style: TextStyle(
              color: Color(0xCC04201C),
              fontSize: 15,
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMessageBubble(_AgentMessage message) {
    final isUser = message.role == _AgentRole.user;
    final bubbleColor =
        isUser ? AppTheme.primaryColor : AppTheme.surfaceColorLight;
    final textColor = isUser ? const Color(0xFF04201C) : Colors.white;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Align(
        alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxWidth: MediaQuery.sizeOf(context).width * 0.84,
          ),
          child: Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: bubbleColor,
              borderRadius: BorderRadius.circular(8),
              border: isUser ? null : Border.all(color: AppTheme.outlineColor),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                MarkdownText(
                  message.content,
                  style: TextStyle(
                    color: textColor,
                    height: 1.5,
                    fontWeight: isUser ? FontWeight.w700 : FontWeight.w400,
                  ),
                ),
                if (!isUser && message.suggestions.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: message.suggestions.map((suggestion) {
                      return ActionChip(
                        label: Text(suggestion),
                        labelStyle: const TextStyle(
                          color: Colors.white,
                          fontSize: 12,
                        ),
                        backgroundColor:
                            AppTheme.primaryColor.withValues(alpha: 0.12),
                        side: BorderSide(
                          color: AppTheme.primaryColor.withValues(alpha: 0.32),
                        ),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(8),
                        ),
                        onPressed:
                            _isSending ? null : () => _sendMessage(suggestion),
                      );
                    }).toList(),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildTypingBubble() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Align(
        alignment: Alignment.centerLeft,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: BoxDecoration(
            color: AppTheme.surfaceColorLight,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: AppTheme.outlineColor),
          ),
          child: const Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: AppTheme.primaryColor,
                ),
              ),
              SizedBox(width: 10),
              Text('助手正在分析...', style: TextStyle(color: Colors.white70)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildInputArea() {
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 8),
      padding: const EdgeInsets.fromLTRB(16, 6, 8, 6),
      decoration: BoxDecoration(
        color: AppTheme.surfaceColor,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.outlineColor),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.22),
            blurRadius: 18,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: TextField(
              controller: _messageController,
              minLines: 1,
              maxLines: 5,
              maxLength: 1000,
              enabled: !_isSending,
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                hintText: '向反诈助手提问...',
                hintStyle:
                    TextStyle(color: Colors.white.withValues(alpha: 0.4)),
                border: InputBorder.none,
                counterText: '',
              ),
              onSubmitted: (_) => _isSending ? null : _sendCurrentMessage(),
            ),
          ),
          const SizedBox(width: 8),
          FloatingActionButton.small(
            key: const ValueKey('send-agent-message-button'),
            tooltip: '发送消息',
            onPressed: _isSending ? null : _sendCurrentMessage,
            backgroundColor: AppTheme.primaryColor,
            foregroundColor: const Color(0xFF04201C),
            child: _isSending
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Color(0xFF04201C),
                    ),
                  )
                : const Icon(Icons.arrow_upward_rounded),
          ),
        ],
      ),
    );
  }

  Future<void> _sendCurrentMessage() async {
    await _sendMessage(_messageController.text.trim());
  }

  Future<void> _sendMessage(String content) async {
    final message = content.trim();
    if (message.isEmpty || _isSending) return;

    setState(() {
      _messages.add(_AgentMessage.user(message));
      _isSending = true;
    });
    _messageController.clear();
    _scrollToBottom();

    try {
      final response = await _agentApi.chat(
        message: message,
        conversationId: _conversationId,
      );

      if (!mounted) return;
      setState(() {
        _conversationId = response.conversationId.isEmpty
            ? _conversationId
            : response.conversationId;
        _messages.add(_AgentMessage.assistant(
          response.message.isEmpty ? '我暂时没有生成有效回复，请稍后再试。' : response.message,
          suggestions: response.suggestions,
        ));
        _isSending = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _messages.add(_AgentMessage.assistant('助手暂时无法回复：$e'));
        _isSending = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('助手对话失败：$e')),
      );
    }

    _scrollToBottom();
  }

  void _startNewChat() {
    setState(() {
      _messages.clear();
      _conversationId = null;
      _isSending = false;
    });
    _messageController.clear();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 260),
        curve: Curves.easeOut,
      );
    });
  }

  IconData _suggestionIcon(String suggestion) {
    if (suggestion.contains('保证金')) {
      return Icons.account_balance_wallet_outlined;
    }
    if (suggestion.contains('客服')) return Icons.verified_user_outlined;
    return Icons.public_outlined;
  }

  String _suggestionSubtitle(String suggestion) {
    if (suggestion.contains('保证金')) {
      return '判断是否存在刷单、贷款、投资类诱导';
    }
    if (suggestion.contains('客服')) {
      return '核验身份冒充、退款话术和远程控制风险';
    }
    return '分析钓鱼页面、诱导下载和收款陷阱';
  }
}

enum _AgentRole { user, assistant }

class _AgentMessage {
  final _AgentRole role;
  final String content;
  final List<String> suggestions;

  const _AgentMessage({
    required this.role,
    required this.content,
    this.suggestions = const [],
  });

  factory _AgentMessage.user(String content) {
    return _AgentMessage(role: _AgentRole.user, content: content);
  }

  factory _AgentMessage.assistant(
    String content, {
    List<String> suggestions = const [],
  }) {
    return _AgentMessage(
      role: _AgentRole.assistant,
      content: content,
      suggestions: suggestions,
    );
  }
}

class _SuggestionTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  const _SuggestionTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: AppTheme.surfaceColor,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.outlineColor),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(8),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: AppTheme.primaryColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, color: AppTheme.primaryColor),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      subtitle,
                      style: const TextStyle(
                        color: Colors.white60,
                        fontSize: 13,
                        height: 1.35,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              const Icon(
                Icons.arrow_forward_ios_rounded,
                size: 16,
                color: Colors.white38,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

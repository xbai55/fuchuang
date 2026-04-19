import 'package:flutter/material.dart';

import '../../../data/api/fraud_api.dart';
import '../../theme/app_theme.dart';
import '../../widgets/markdown_text.dart';
import '../agent/agent_page.dart';
import '../home/home_page.dart';

/// 历史记录页面
class HistoryPage extends StatefulWidget {
  const HistoryPage({super.key});

  @override
  State<HistoryPage> createState() => _HistoryPageState();
}

class _HistoryPageState extends State<HistoryPage> {
  final FraudApi _fraudApi = FraudApi();
  final List<DetectionHistory> _history = [];

  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    if (!_isLoading) {
      setState(() {
        _isLoading = true;
        _error = null;
      });
    }

    try {
      final result = await _fraudApi.getHistory(size: 50);
      if (!mounted) return;
      setState(() {
        _history
          ..clear()
          ..addAll(result.items);
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _error = e.toString();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.backgroundColor,
      appBar: AppBar(
        title: const Text('历史记录'),
        actions: [
          IconButton(
            tooltip: '刷新',
            icon: const Icon(Icons.refresh),
            onPressed: _loadHistory,
          ),
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
          color: AppTheme.primaryColor,
          backgroundColor: AppTheme.surfaceColor,
          onRefresh: _loadHistory,
          child: _buildBody(),
        ),
      ),
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return ListView(
        padding: const EdgeInsets.all(20),
        children: const [
          SizedBox(height: 180),
          Center(
            child: CircularProgressIndicator(color: AppTheme.primaryColor),
          ),
        ],
      );
    }

    if (_error != null) {
      return ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _buildInfoCard(),
          const SizedBox(height: 80),
          const Icon(
            Icons.cloud_off_rounded,
            size: 58,
            color: AppTheme.warningColor,
          ),
          const SizedBox(height: 16),
          const Text(
            '历史记录加载失败',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Colors.white,
              fontSize: 20,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            _error!,
            textAlign: TextAlign.center,
            maxLines: 4,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: Colors.white60, height: 1.45),
          ),
          const SizedBox(height: 20),
          ElevatedButton.icon(
            onPressed: _loadHistory,
            icon: const Icon(Icons.refresh),
            label: const Text('重新加载'),
          ),
        ],
      );
    }

    if (_history.isEmpty) {
      return ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _buildInfoCard(),
          const SizedBox(height: 90),
          Container(
            width: 84,
            height: 84,
            decoration: BoxDecoration(
              color: AppTheme.primaryColor.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: AppTheme.primaryColor.withValues(alpha: 0.24),
              ),
            ),
            child: Icon(
              Icons.history_rounded,
              size: 42,
              color: AppTheme.primaryColor.withValues(alpha: 0.9),
            ),
          ),
          const SizedBox(height: 22),
          const Text(
            '暂无历史记录',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.w900,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 10),
          const Text(
            '完成一次风险检测后，结果会自动保存在这里。',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 15,
              height: 1.5,
              color: Colors.white60,
            ),
          ),
        ],
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      itemCount: _history.length + 1,
      separatorBuilder: (context, index) => const SizedBox(height: 12),
      itemBuilder: (context, index) {
        if (index == 0) return _buildInfoCard();
        return _buildHistoryItem(_history[index - 1]);
      },
    );
  }

  Widget _buildInfoCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppTheme.surfaceColor,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.outlineColor),
      ),
      child: const Row(
        children: [
          Icon(Icons.insights_rounded, color: AppTheme.primaryColor),
          SizedBox(width: 12),
          Expanded(
            child: Text(
              '检测完成后，可在这里回看风险结论、诈骗类型和处置建议。',
              style: TextStyle(
                color: Colors.white70,
                height: 1.45,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHistoryItem(DetectionHistory item) {
    final riskColor = item.chatMode == 'agent'
        ? AppTheme.primaryColor
        : _riskColor(item.riskLevel);

    return InkWell(
      borderRadius: BorderRadius.circular(8),
      onTap: () => _openHistoryItem(item),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppTheme.surfaceColor,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: AppTheme.outlineColor),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: riskColor.withValues(alpha: 0.14),
                    borderRadius: BorderRadius.circular(8),
                    border:
                        Border.all(color: riskColor.withValues(alpha: 0.45)),
                  ),
                  child: Text(
                    item.chatMode == 'agent'
                        ? '助手对话'
                        : _riskText(item.riskLevel),
                    style: TextStyle(
                      color: riskColor,
                      fontSize: 12,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    item.chatMode == 'agent' ? '反诈助手' : '风险分 ${item.riskScore}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: Colors.white70,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  _formatTime(item.createdAt),
                  style: const TextStyle(color: Colors.white38, fontSize: 12),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              item.userMessage.isEmpty ? '文件内容检测' : item.userMessage,
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: Colors.white,
                height: 1.45,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 10),
            Text(
              cleanMarkdownText(
                  item.botResponse.isEmpty ? item.scamType : item.botResponse),
              key: ValueKey('history-response-${item.id}'),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(color: Colors.white60, height: 1.45),
            ),
            if (item.scamType.isNotEmpty) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  const Icon(Icons.category,
                      size: 16, color: AppTheme.accentColor),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      item.scamType,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: AppTheme.accentColor,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  Color _riskColor(String riskLevel) {
    switch (riskLevel) {
      case 'high':
        return AppTheme.errorColor;
      case 'medium':
        return AppTheme.warningColor;
      case 'low':
        return AppTheme.successColor;
      default:
        return Colors.white54;
    }
  }

  String _riskText(String riskLevel) {
    switch (riskLevel) {
      case 'high':
        return '高风险';
      case 'medium':
        return '中风险';
      case 'low':
        return '低风险';
      default:
        return '未知';
    }
  }

  String _formatTime(DateTime time) {
    final local = time.toLocal();
    String two(int value) => value.toString().padLeft(2, '0');
    return '${two(local.month)}-${two(local.day)} ${two(local.hour)}:${two(local.minute)}';
  }

  void _openHistoryItem(DetectionHistory item) {
    final userMessage = item.userMessage.isEmpty ? '文件内容检测' : item.userMessage;
    final assistantMessage = cleanMarkdownText(
        item.botResponse.isEmpty ? item.scamType : item.botResponse);

    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) {
          if (item.chatMode == 'agent') {
            return AgentPage(
              initialUserMessage: userMessage,
              initialAssistantMessage: assistantMessage,
            );
          }
          return HomePage(
            initialUserMessage: userMessage,
            initialAssistantMessage: assistantMessage,
          );
        },
      ),
    );
  }
}

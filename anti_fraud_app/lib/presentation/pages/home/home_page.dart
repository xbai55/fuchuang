import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/utils/emergency_actions.dart';
import '../../../data/models/detection_result.dart';
import '../../blocs/detection/detection_bloc.dart';
import '../../theme/app_appearance.dart';
import '../../theme/app_locale.dart';
import '../../theme/app_theme.dart';
import '../../widgets/markdown_text.dart';
import '../result/result_page.dart';

/// 首页 - 对话式风险检测界面
class HomePage extends StatefulWidget {
  final String? initialUserMessage;
  final String? initialAssistantMessage;

  const HomePage({
    super.key,
    this.initialUserMessage,
    this.initialAssistantMessage,
  });

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> with TickerProviderStateMixin {
  final TextEditingController _messageController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final ImagePicker _imagePicker = ImagePicker();
  final List<_ChatMessage> _messages = [];

  final List<File> _selectedImages = [];
  final List<File> _selectedAudios = [];
  final List<File> _selectedVideos = [];

  late AnimationController _glowController;

  bool get _hasSelectedFiles =>
      _selectedImages.isNotEmpty ||
      _selectedAudios.isNotEmpty ||
      _selectedVideos.isNotEmpty;

  @override
  void initState() {
    super.initState();
    if (widget.initialUserMessage != null ||
        widget.initialAssistantMessage != null) {
      if ((widget.initialUserMessage ?? '').trim().isNotEmpty) {
        _messages.add(_ChatMessage.user(widget.initialUserMessage!.trim()));
      }
      if ((widget.initialAssistantMessage ?? '').trim().isNotEmpty) {
        _messages.add(
          _ChatMessage.assistantText(widget.initialAssistantMessage!.trim()),
        );
      }
    }
    _glowController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _messageController.dispose();
    _scrollController.dispose();
    _glowController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (context) => DetectionBloc(),
      child: BlocListener<DetectionBloc, DetectionState>(
        listener: (context, state) {
          if (state is DetectionSuccess) {
            _appendAssistantResult(state.result);
          } else if (state is DetectionError) {
            _appendAssistantError(state.error);
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(
                  '${AppLocale.text('检测失败', 'Detection failed')}：${state.error}',
                ),
              ),
            );
          }
        },
        child: Scaffold(
          backgroundColor: AppTheme.backgroundColor,
          body: Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  const Color(0xFF0D211D),
                  AppTheme.backgroundColor,
                  AppTheme.backgroundColor,
                ],
              ),
            ),
            child: SafeArea(
              child: Column(
                children: [
                  _buildHeader(),
                  Expanded(child: _buildContent()),
                  _buildInputArea(),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          AnimatedBuilder(
            animation: _glowController,
            builder: (context, child) {
              return Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(8),
                  gradient: AppTheme.primaryGradient,
                  boxShadow: [
                    BoxShadow(
                      color: AppTheme.primaryColor.withValues(
                        alpha: 0.22 + _glowController.value * 0.16,
                      ),
                      blurRadius: 18 + _glowController.value * 8,
                      spreadRadius: 1,
                    ),
                  ],
                ),
                clipBehavior: Clip.antiAlias,
                child: Image.asset(
                  'assets/images/fclogo.png',
                  fit: BoxFit.cover,
                ),
              );
            },
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  ApiConstants.appName,
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w800,
                      ),
                ),
                const SizedBox(height: 4),
                Text(
                  AppLocale.text(
                    '识别短信、通话、图片和视频里的诈骗风险',
                    'Identify scam risks in messages, calls, images, and videos',
                  ),
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Colors.white60,
                        height: 1.35,
                      ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          IconButton(
            tooltip: AppLocale.text('新建聊天', 'New Chat'),
            icon: const Icon(Icons.add_comment_outlined, color: Colors.white70),
            onPressed: _startNewChat,
          ),
        ],
      ),
    );
  }

  Widget _buildContent() {
    return BlocBuilder<DetectionBloc, DetectionState>(
      builder: (context, state) {
        final isDetecting = state is Detecting;

        if (_messages.isEmpty && !isDetecting) {
          return SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildRiskSummaryCard(),
                const SizedBox(height: 16),
                _buildQuickActions(),
              ],
            ),
          );
        }

        return ListView.builder(
          controller: _scrollController,
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 20),
          itemCount: _messages.length + (isDetecting ? 1 : 0),
          itemBuilder: (context, index) {
            if (index == _messages.length) {
              return _buildDetectingBubble(state as Detecting);
            }
            return _buildChatBubble(_messages[index]);
          },
        );
      },
    );
  }

  Widget _buildRiskSummaryCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppTheme.surfaceColor.withValues(alpha: 0.88),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.outlineColor),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: AppTheme.primaryColor.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.radar_rounded,
                  color: AppTheme.primaryColor,
                ),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Text(
                  '把可疑内容交给 AI，先看风险再行动',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                    height: 1.35,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          const Row(
            children: [
              Expanded(
                child: _SignalItem(label: '转账诱导', icon: Icons.payments),
              ),
              SizedBox(width: 8),
              Expanded(
                child: _SignalItem(label: '身份冒充', icon: Icons.badge),
              ),
              SizedBox(width: 8),
              Expanded(
                child: _SignalItem(label: '链接钓鱼', icon: Icons.link),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildQuickActions() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          AppLocale.text('快速检测', 'Quick Checks'),
          style: const TextStyle(
            color: Colors.white,
            fontSize: 16,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 10),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: [
            _QuickActionChip(
              icon: Icons.mic,
              label: AppLocale.text('语音分析', 'Audio'),
              onTap: _pickAudio,
            ),
            _QuickActionChip(
              icon: Icons.image,
              label: AppLocale.text('图片识别', 'Images'),
              onTap: _pickImage,
            ),
            _QuickActionChip(
              icon: Icons.videocam,
              label: AppLocale.text('视频检测', 'Video'),
              onTap: _pickVideo,
            ),
            _QuickActionChip(
              icon: Icons.chat,
              label: AppLocale.text('聊天记录', 'Chat Log'),
              onTap: () {
                _messageController.text =
                    '你好，我是淘宝客服，您的订单有问题需要退款，请先点击链接填写银行卡信息。';
              },
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildSelectedFilesPreview() {
    if (!_hasSelectedFiles) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          AppLocale.text('已选文件', 'Selected Files'),
          style: const TextStyle(
            color: Colors.white60,
            fontSize: 14,
          ),
        ),
        const SizedBox(height: 12),
        SizedBox(
          height: 92,
          child: ListView(
            scrollDirection: Axis.horizontal,
            children: [
              for (var index = 0; index < _selectedImages.length; index++)
                _ImageAttachmentPreview(
                  file: _selectedImages[index],
                  onDelete: () {
                    setState(() => _selectedImages.removeAt(index));
                  },
                ),
              for (var index = 0; index < _selectedAudios.length; index++)
                _MediaAttachmentPreview(
                  icon: Icons.mic,
                  label: '${AppLocale.text('语音', 'Audio')} ${index + 1}',
                  fileName: _selectedAudios[index]
                      .path
                      .split(Platform.pathSeparator)
                      .last,
                  onDelete: () {
                    setState(() => _selectedAudios.removeAt(index));
                  },
                ),
              for (var index = 0; index < _selectedVideos.length; index++)
                _MediaAttachmentPreview(
                  icon: Icons.videocam,
                  label: '${AppLocale.text('视频', 'Video')} ${index + 1}',
                  fileName: _selectedVideos[index]
                      .path
                      .split(Platform.pathSeparator)
                      .last,
                  onDelete: () {
                    setState(() => _selectedVideos.removeAt(index));
                  },
                ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildChatBubble(_ChatMessage message) {
    final isUser = message.role == _ChatRole.user;
    final bubbleColor =
        isUser ? AppTheme.primaryColor : AppTheme.surfaceColorLight;
    final foregroundColor = isUser ? const Color(0xFF04201C) : Colors.white;

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
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.12),
                  blurRadius: 12,
                  offset: const Offset(0, 6),
                ),
              ],
            ),
            child: message.result == null
                ? MarkdownText(
                    message.content,
                    style: TextStyle(
                      color: foregroundColor,
                      height: 1.45,
                      fontWeight: isUser ? FontWeight.w600 : FontWeight.w400,
                    ),
                  )
                : _buildResultMessage(message.result!),
          ),
        ),
      ),
    );
  }

  Widget _buildResultMessage(DetectionResult result) {
    final riskColor = _riskColor(result.riskLevel);
    final actionItems = _actionItems(result.riskLevel);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: riskColor.withValues(alpha: 0.16),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: riskColor.withValues(alpha: 0.48)),
              ),
              child: Text(
                result.riskLevelText,
                style: TextStyle(
                  color: riskColor,
                  fontWeight: FontWeight.w900,
                  fontSize: 13,
                ),
              ),
            ),
            const SizedBox(width: 10),
            Text(
              '风险分 ${result.riskScore}',
              style: const TextStyle(
                color: Colors.white70,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        _ResultLine(
          label: '诈骗类型',
          value: result.scamType.isEmpty ? '暂未识别明确类型' : result.scamType,
        ),
        const SizedBox(height: 10),
        Text(
          result.warningMessage.isEmpty
              ? '未发现明显高危特征，但仍建议核实来源后再继续操作。'
              : cleanMarkdownText(result.warningMessage),
          style: const TextStyle(
            color: Colors.white,
            height: 1.5,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 12),
        const Text(
          '建议操作',
          style: TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 8),
        ...actionItems.map(
          (item) => Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.check_circle, size: 16, color: riskColor),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    item,
                    style: const TextStyle(
                      color: Colors.white70,
                      height: 1.35,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
        if (result.finalReport.isNotEmpty) ...[
          const SizedBox(height: 6),
          Theme(
            data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
            child: ExpansionTile(
              tilePadding: EdgeInsets.zero,
              childrenPadding: EdgeInsets.zero,
              iconColor: AppTheme.primaryColor,
              collapsedIconColor: Colors.white60,
              title: const Text(
                '查看完整分析',
                style: TextStyle(
                  color: AppTheme.primaryColor,
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                ),
              ),
              children: [
                Align(
                  alignment: Alignment.centerLeft,
                  child: MarkdownText(
                    result.finalReport,
                    style: const TextStyle(
                      color: Colors.white70,
                      height: 1.55,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildDetectingBubble(Detecting state) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Align(
        alignment: Alignment.centerLeft,
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxWidth: MediaQuery.sizeOf(context).width * 0.84,
          ),
          child: Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppTheme.surfaceColorLight,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppTheme.outlineColor),
            ),
            child: Row(
              children: [
                SizedBox(
                  width: 34,
                  height: 34,
                  child: CircularProgressIndicator(
                    value: state.progress / 100,
                    strokeWidth: 3,
                    backgroundColor: Colors.white12,
                    valueColor: const AlwaysStoppedAnimation<Color>(
                      AppTheme.primaryColor,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    state.isAsync ? 'AI 正在深度分析，请稍候...' : '正在上传并识别内容...',
                    style: const TextStyle(
                      color: Colors.white70,
                      height: 1.4,
                    ),
                  ),
                ),
                Text(
                  '${state.progress}%',
                  style: const TextStyle(
                    color: AppTheme.primaryColor,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildInputArea() {
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 8),
      padding: const EdgeInsets.fromLTRB(4, 4, 4, 8),
      decoration: BoxDecoration(
        color: AppTheme.surfaceColor,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: AppTheme.outlineColor,
          width: 1,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.22),
            blurRadius: 18,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        children: [
          if (_hasSelectedFiles)
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
              child: _buildSelectedFilesPreview(),
            ),
          TextField(
            controller: _messageController,
            minLines: 1,
            maxLines: null,
            maxLength: 1000,
            style: const TextStyle(color: Colors.white),
            decoration: InputDecoration(
              hintText: '输入可疑的对话、短信或描述...',
              hintStyle: TextStyle(color: Colors.white.withValues(alpha: 0.4)),
              border: InputBorder.none,
              contentPadding: const EdgeInsets.symmetric(
                horizontal: 20,
                vertical: 16,
              ),
              counterStyle:
                  TextStyle(color: Colors.white.withValues(alpha: 0.3)),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Row(
              children: [
                _InputIconButton(
                  icon: Icons.image_outlined,
                  tooltip: '选择图片',
                  onPressed: _pickImage,
                ),
                _InputIconButton(
                  icon: Icons.mic_none,
                  tooltip: '选择语音',
                  onPressed: _pickAudio,
                ),
                _InputIconButton(
                  icon: Icons.videocam_outlined,
                  tooltip: '选择视频',
                  onPressed: _pickVideo,
                ),
                const Spacer(),
                BlocBuilder<DetectionBloc, DetectionState>(
                  builder: (blocContext, state) {
                    final isLoading = state is Detecting;
                    return FloatingActionButton.small(
                      key: const ValueKey('send-detection-button'),
                      tooltip: '发送检测',
                      onPressed:
                          isLoading ? null : () => _startDetection(blocContext),
                      backgroundColor: AppTheme.primaryColor,
                      foregroundColor: const Color(0xFF04201C),
                      child: isLoading
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Color(0xFF04201C),
                              ),
                            )
                          : const Icon(Icons.arrow_upward_rounded),
                    );
                  },
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _pickImage() async {
    final picked = await _imagePicker.pickMultiImage();
    if (picked.isNotEmpty) {
      setState(() {
        _selectedImages.addAll(picked.map((file) => File(file.path)));
      });
    }
  }

  Future<void> _pickAudio() async {
    final result = await FilePicker.pickFiles(
      type: FileType.audio,
      allowMultiple: true,
    );
    if (result != null) {
      final files = result.files
          .where((file) => file.path != null)
          .map((file) => File(file.path!))
          .toList();
      if (files.isEmpty) return;
      setState(() {
        _selectedAudios.addAll(files);
      });
    }
  }

  Future<void> _pickVideo() async {
    final result = await FilePicker.pickFiles(
      type: FileType.video,
      allowMultiple: true,
    );
    if (result != null) {
      final files = result.files
          .where((file) => file.path != null)
          .map((file) => File(file.path!))
          .toList();
      if (files.isEmpty) return;
      setState(() {
        _selectedVideos.addAll(files);
      });
    }
  }

  void _startDetection(BuildContext blocContext) {
    final message = _messageController.text.trim();
    final imageFile = _selectedImages.isNotEmpty ? _selectedImages.first : null;
    final audioFile = _selectedAudios.isNotEmpty ? _selectedAudios.first : null;
    final videoFile = _selectedVideos.isNotEmpty ? _selectedVideos.first : null;
    final hasFiles =
        imageFile != null || audioFile != null || videoFile != null;

    if (message.isEmpty && !hasFiles) {
      ScaffoldMessenger.of(blocContext).showSnackBar(
        const SnackBar(content: Text('请输入内容或选择文件')),
      );
      return;
    }

    final userContent = _buildUserMessageText(message, hasFiles);
    final isLargeFile = videoFile != null ||
        (audioFile != null && audioFile.lengthSync() > 5 * 1024 * 1024);

    setState(() {
      _messages.add(_ChatMessage.user(userContent));
      _selectedImages.clear();
      _selectedAudios.clear();
      _selectedVideos.clear();
    });
    _messageController.clear();
    _scrollToBottom();

    final bloc = blocContext.read<DetectionBloc>();

    if (isLargeFile) {
      bloc.add(StartAsyncDetection(
        message: message,
        audioFile: audioFile,
        imageFile: imageFile,
        videoFile: videoFile,
      ));
    } else {
      bloc.add(StartDetection(
        message: message,
        audioFile: audioFile,
        imageFile: imageFile,
        videoFile: videoFile,
      ));
    }
  }

  String _buildUserMessageText(String message, bool hasFiles) {
    final fileLabels = [
      if (_selectedImages.isNotEmpty) '图片 ${_selectedImages.length} 张',
      if (_selectedAudios.isNotEmpty) '语音 ${_selectedAudios.length} 个',
      if (_selectedVideos.isNotEmpty) '视频 ${_selectedVideos.length} 个',
    ];

    if (message.isNotEmpty && hasFiles) {
      return '$message\n\n已附加：${fileLabels.join('、')}';
    }
    if (message.isNotEmpty) return message;
    return '请分析我上传的${fileLabels.join('、')}内容。';
  }

  void _appendAssistantResult(DetectionResult result) {
    if (!mounted) return;

    setState(() {
      _messages.add(_ChatMessage.assistant(result));
    });
    _scrollToBottom();

    if (result.isHighRisk || result.isMediumRisk) {
      EmergencyActions.speakRiskWarning(
        riskLevel: result.riskLevel,
        isEnglish: AppAppearance.instance.isEnglish,
      );
    }

    if (result.isHighRisk) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _showHighRiskDialog(result);
      });
    }
  }

  void _appendAssistantError(String error) {
    if (!mounted) return;
    setState(() {
      _messages.add(_ChatMessage.assistantText('检测失败：$error'));
    });
    _scrollToBottom();
  }

  Future<void> _dialNumber(String number) async {
    final ok = await EmergencyActions.dial(number);
    if (!mounted) return;

    if (!ok) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(AppLocale.text(
            '\u65e0\u6cd5\u6253\u5f00\u62e8\u53f7\u5668\uff0c\u8bf7\u624b\u52a8\u62e8\u6253 $number',
            'Unable to open dialer. Please call $number manually.',
          )),
        ),
      );
    }
  }

  void _replayVoiceWarning(DetectionResult result) {
    EmergencyActions.speakRiskWarning(
      riskLevel: result.riskLevel,
      isEnglish: AppAppearance.instance.isEnglish,
    );
  }

  void _showHighRiskDialog(DetectionResult result) {
    showDialog<void>(
      context: context,
      builder: (dialogContext) {
        final guardianAction = result.guardianCallAction;
        return AlertDialog(
          backgroundColor: AppTheme.surfaceColor,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
            side: const BorderSide(color: AppTheme.errorColor),
          ),
          title: Row(
            children: [
              const Icon(Icons.warning_amber_rounded,
                  color: AppTheme.errorColor),
              const SizedBox(width: 10),
              Text(AppLocale.text('\u9ad8\u98ce\u9669\u9884\u8b66', 'High Risk Alert')),
            ],
          ),
          content: Text(
            result.warningMessage.isEmpty
                ? AppLocale.text(
                    '\u68c0\u6d4b\u7ed3\u679c\u4e3a\u9ad8\u98ce\u9669\uff0c\u8bf7\u7acb\u5373\u505c\u6b62\u8f6c\u8d26\u548c\u5171\u4eab\u5c4f\u5e55\uff0c\u5e76\u8054\u7cfb\u76d1\u62a4\u4eba\u6216\u62e8\u6253\u53cd\u8bc8\u4e13\u7ebf\u3002',
                    'The result is high risk. Stop transfers and screen sharing, then contact your guardian or the anti-fraud hotline.',
                  )
                : result.warningMessage,
            style: const TextStyle(color: Colors.white70, height: 1.5),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: Text(AppLocale.text('\u5173\u95ed', 'Close')),
            ),
            TextButton.icon(
              onPressed: () => _replayVoiceWarning(result),
              icon: const Icon(Icons.volume_up_outlined),
              label: Text(AppLocale.text('\u8bed\u97f3\u8b66\u793a', 'Voice Warning')),
            ),
            TextButton.icon(
              onPressed: () {
                Navigator.pop(dialogContext);
                _dialNumber('96110');
              },
              icon: const Icon(Icons.phone_outlined),
              label: Text(AppLocale.text('\u62e8\u6253 96110', 'Call 96110')),
            ),
            if (guardianAction != null)
              TextButton.icon(
                onPressed: () {
                  Navigator.pop(dialogContext);
                  _dialNumber(guardianAction.value);
                },
                icon: const Icon(Icons.contact_phone_outlined),
                label: Text(guardianAction.label.isEmpty
                    ? AppLocale.text('\u8054\u7cfb\u76d1\u62a4\u4eba', 'Contact Guardian')
                    : guardianAction.label),
              ),
            ElevatedButton.icon(
              onPressed: () {
                Navigator.pop(dialogContext);
                _dialNumber('110');
              },
              icon: const Icon(Icons.local_police_outlined),
              label: Text(AppLocale.text('\u62e8\u6253 110', 'Call 110')),
            ),
            ElevatedButton(
              onPressed: () {
                Navigator.pop(dialogContext);
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (context) => ResultPage(result: result),
                  ),
                );
              },
              child: Text(AppLocale.text('\u67e5\u770b\u8be6\u60c5', 'View Details')),
            ),
          ],
        );
      },
    );
  }

  void _startNewChat() {
    setState(() {
      _messages.clear();
      _selectedImages.clear();
      _selectedAudios.clear();
      _selectedVideos.clear();
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

  List<String> _actionItems(String riskLevel) {
    switch (riskLevel) {
      case 'high':
        return const [
          '立即停止转账、验证码填写或屏幕共享。',
          '通过官方电话、App 或线下渠道核实身份。',
          '保留聊天记录并提醒家人共同判断。',
        ];
      case 'medium':
        return const [
          '不要点击陌生链接，也不要安装对方提供的软件。',
          '先核实对方身份，再决定是否继续沟通。',
          '涉及钱款或证件信息时提高警惕。',
        ];
      default:
        return const [
          '当前风险较低，但仍建议确认来源可靠。',
          '不要向陌生人透露验证码、密码或完整证件号。',
          '后续出现转账或威胁话术时重新检测。',
        ];
    }
  }
}

enum _ChatRole { user, assistant }

class _ChatMessage {
  final _ChatRole role;
  final String content;
  final DetectionResult? result;

  const _ChatMessage({
    required this.role,
    required this.content,
    this.result,
  });

  factory _ChatMessage.user(String content) {
    return _ChatMessage(role: _ChatRole.user, content: content);
  }

  factory _ChatMessage.assistant(DetectionResult result) {
    return _ChatMessage(
      role: _ChatRole.assistant,
      content: result.warningMessage,
      result: result,
    );
  }

  factory _ChatMessage.assistantText(String content) {
    return _ChatMessage(role: _ChatRole.assistant, content: content);
  }
}

class _ResultLine extends StatelessWidget {
  final String label;
  final String value;

  const _ResultLine({
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '$label：',
          style: const TextStyle(
            color: Colors.white54,
            fontWeight: FontWeight.w700,
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ],
    );
  }
}

class _SignalItem extends StatelessWidget {
  final String label;
  final IconData icon;

  const _SignalItem({
    required this.label,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minHeight: 68),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, color: AppTheme.accentColor, size: 20),
          const SizedBox(height: 6),
          Text(
            label,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: Colors.white70,
              fontSize: 12,
              height: 1.2,
            ),
          ),
        ],
      ),
    );
  }
}

class _InputIconButton extends StatelessWidget {
  final IconData icon;
  final String tooltip;
  final VoidCallback onPressed;

  const _InputIconButton({
    required this.icon,
    required this.tooltip,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return IconButton(
      tooltip: tooltip,
      constraints: const BoxConstraints(minWidth: 44, minHeight: 44),
      icon: Icon(icon, color: Colors.white70),
      onPressed: onPressed,
    );
  }
}

class _QuickActionChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _QuickActionChip({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return ActionChip(
      avatar: Icon(icon, size: 18, color: AppTheme.primaryColor),
      label: Text(label),
      labelStyle: const TextStyle(
        color: Colors.white,
        fontSize: 13,
        fontWeight: FontWeight.w600,
      ),
      backgroundColor: AppTheme.surfaceColorLight,
      side: BorderSide(color: AppTheme.outlineColor),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
      onPressed: onTap,
    );
  }
}

class _ImageAttachmentPreview extends StatelessWidget {
  final File file;
  final VoidCallback onDelete;

  const _ImageAttachmentPreview({
    required this.file,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 86,
      height: 86,
      margin: const EdgeInsets.only(right: 8),
      child: Stack(
        children: [
          Positioned.fill(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: Image.file(
                file,
                fit: BoxFit.cover,
                errorBuilder: (context, error, stackTrace) {
                  return Container(
                    color: AppTheme.surfaceColorLight,
                    child: const Icon(
                      Icons.broken_image_outlined,
                      color: Colors.white54,
                    ),
                  );
                },
              ),
            ),
          ),
          Positioned(
            top: 4,
            right: 4,
            child: _AttachmentDeleteButton(onPressed: onDelete),
          ),
        ],
      ),
    );
  }
}

class _MediaAttachmentPreview extends StatelessWidget {
  final IconData icon;
  final String label;
  final String fileName;
  final VoidCallback onDelete;

  const _MediaAttachmentPreview({
    required this.icon,
    required this.label,
    required this.fileName,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 136,
      height: 86,
      margin: const EdgeInsets.only(right: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AppTheme.surfaceColorLight,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.outlineColor),
      ),
      child: Stack(
        children: [
          Positioned.fill(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(icon, color: AppTheme.primaryColor, size: 22),
                const SizedBox(height: 8),
                Text(
                  label,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  fileName,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: Colors.white54, fontSize: 11),
                ),
              ],
            ),
          ),
          Positioned(
            top: 0,
            right: 0,
            child: _AttachmentDeleteButton(onPressed: onDelete),
          ),
        ],
      ),
    );
  }
}

class _AttachmentDeleteButton extends StatelessWidget {
  final VoidCallback onPressed;

  const _AttachmentDeleteButton({required this.onPressed});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onPressed,
      borderRadius: BorderRadius.circular(8),
      child: Container(
        width: 24,
        height: 24,
        decoration: BoxDecoration(
          color: Colors.black.withValues(alpha: 0.58),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: Colors.white24),
        ),
        child: const Icon(Icons.close, color: Colors.white, size: 16),
      ),
    );
  }
}

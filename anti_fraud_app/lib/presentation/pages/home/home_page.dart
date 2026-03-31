import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:image_picker/image_picker.dart';
import 'package:file_picker/file_picker.dart';

import '../../blocs/detection/detection_bloc.dart';
import '../../theme/app_theme.dart';
import '../result/result_page.dart';

/// 首页 - 仿 Gemini 风格的对话式检测界面
class HomePage extends StatefulWidget {
  const HomePage({Key? key}) : super(key: key);

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> with TickerProviderStateMixin {
  final TextEditingController _messageController = TextEditingController();
  final ImagePicker _imagePicker = ImagePicker();

  // 选中的文件
  File? _selectedImage;
  File? _selectedAudio;
  File? _selectedVideo;

  // 动画控制器
  late AnimationController _glowController;

  @override
  void initState() {
    super.initState();
    _glowController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _messageController.dispose();
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
            // 跳转到结果页
            Navigator.push(
              context,
              MaterialPageRoute(
                builder: (context) => ResultPage(result: state.result),
              ),
            );
          } else if (state is DetectionError) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('检测失败: ${state.error}')),
            );
          }
        },
        child: Scaffold(
          backgroundColor: AppTheme.backgroundColor,
          body: SafeArea(
            child: Column(
              children: [
                _buildHeader(),
                Expanded(
                  child: _buildContent(),
                ),
                _buildInputArea(),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        children: [
          AnimatedBuilder(
            animation: _glowController,
            builder: (context, child) {
              return Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: LinearGradient(
                    colors: [
                      AppTheme.primaryColor.withOpacity(
                        0.5 + _glowController.value * 0.3,
                      ),
                      AppTheme.secondaryColor.withOpacity(
                        0.3 + _glowController.value * 0.2,
                      ),
                    ],
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: AppTheme.primaryColor.withOpacity(
                        0.3 + _glowController.value * 0.2,
                      ),
                      blurRadius: 20 + _glowController.value * 10,
                      spreadRadius: 2 + _glowController.value * 2,
                    ),
                  ],
                ),
                child: const Icon(
                  Icons.shield,
                  size: 40,
                  color: Colors.white,
                ),
              );
            },
          ),
          const SizedBox(height: 16),
          Text(
            'AI 反诈助手',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                ),
          ),
          const SizedBox(height: 8),
          Text(
            '输入可疑内容，AI 为您识别诈骗风险',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Colors.white60,
                ),
          ),
        ],
      ),
    );
  }

  Widget _buildContent() {
    return BlocBuilder<DetectionBloc, DetectionState>(
      builder: (context, state) {
        if (state is Detecting) {
          return _buildProgressView(state);
        }

        return SingleChildScrollView(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            children: [
              _buildQuickActions(),
              const SizedBox(height: 32),
              _buildSelectedFilesPreview(),
            ],
          ),
        );
      },
    );
  }

  Widget _buildProgressView(Detecting state) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          SizedBox(
            width: 120,
            height: 120,
            child: CircularProgressIndicator(
              value: state.progress / 100,
              strokeWidth: 8,
              backgroundColor: Colors.white12,
              valueColor: AlwaysStoppedAnimation<Color>(
                AppTheme.primaryColor,
              ),
            ),
          ),
          const SizedBox(height: 24),
          Text(
            '${state.progress}%',
            style: const TextStyle(
              fontSize: 32,
              fontWeight: FontWeight.bold,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 16),
          Text(
            state.isAsync ? 'AI 分析中，请稍候...' : '上传文件中...',
            style: const TextStyle(
              fontSize: 16,
              color: Colors.white60,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildQuickActions() {
    return Wrap(
      spacing: 12,
      runSpacing: 12,
      children: [
        _QuickActionChip(
          icon: Icons.mic,
          label: '语音分析',
          onTap: _pickAudio,
        ),
        _QuickActionChip(
          icon: Icons.image,
          label: '图片识别',
          onTap: _pickImage,
        ),
        _QuickActionChip(
          icon: Icons.videocam,
          label: '视频检测',
          onTap: _pickVideo,
        ),
        _QuickActionChip(
          icon: Icons.chat,
          label: '聊天记录',
          onTap: () {
            _messageController.text =
              '你好，我是淘宝客服，您的订单有问题需要退款...';
          },
        ),
      ],
    );
  }

  Widget _buildSelectedFilesPreview() {
    final hasFiles = _selectedImage != null ||
                     _selectedAudio != null ||
                     _selectedVideo != null;

    if (!hasFiles) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '已选文件',
          style: TextStyle(
            color: Colors.white60,
            fontSize: 14,
          ),
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          children: [
            if (_selectedImage != null)
              _FileChip(
                icon: Icons.image,
                label: '图片',
                onDelete: () => setState(() => _selectedImage = null),
              ),
            if (_selectedAudio != null)
              _FileChip(
                icon: Icons.mic,
                label: '语音',
                onDelete: () => setState(() => _selectedAudio = null),
              ),
            if (_selectedVideo != null)
              _FileChip(
                icon: Icons.videocam,
                label: '视频',
                onDelete: () => setState(() => _selectedVideo = null),
              ),
          ],
        ),
      ],
    );
  }

  Widget _buildInputArea() {
    return Container(
      margin: const EdgeInsets.all(16.0),
      padding: const EdgeInsets.all(4.0),
      decoration: BoxDecoration(
        color: AppTheme.surfaceColor,
        borderRadius: BorderRadius.circular(28),
        border: Border.all(
          color: AppTheme.primaryColor.withOpacity(0.3),
          width: 1,
        ),
      ),
      child: Column(
        children: [
          // 输入框
          TextField(
            controller: _messageController,
            maxLines: null,
            maxLength: 1000,
            style: const TextStyle(color: Colors.white),
            decoration: InputDecoration(
              hintText: '输入可疑的对话、短信或描述...',
              hintStyle: TextStyle(color: Colors.white.withOpacity(0.4)),
              border: InputBorder.none,
              contentPadding: const EdgeInsets.symmetric(
                horizontal: 20,
                vertical: 16,
              ),
              counterStyle: TextStyle(color: Colors.white.withOpacity(0.3)),
            ),
          ),

          // 工具栏
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12.0),
            child: Row(
              children: [
                // 上传按钮组
                IconButton(
                  icon: const Icon(Icons.image_outlined, color: Colors.white60),
                  onPressed: _pickImage,
                ),
                IconButton(
                  icon: const Icon(Icons.mic_none, color: Colors.white60),
                  onPressed: _pickAudio,
                ),
                IconButton(
                  icon: const Icon(Icons.videocam_outlined, color: Colors.white60),
                  onPressed: _pickVideo,
                ),

                const Spacer(),

                // 发送按钮
                BlocBuilder<DetectionBloc, DetectionState>(
                  builder: (context, state) {
                    final isLoading = state is Detecting;
                    return FloatingActionButton.small(
                      onPressed: isLoading ? null : _startDetection,
                      backgroundColor: AppTheme.primaryColor,
                      child: isLoading
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : const Icon(Icons.send, color: Colors.white),
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
    final picked = await _imagePicker.pickImage(source: ImageSource.gallery);
    if (picked != null) {
      setState(() {
        _selectedImage = File(picked.path);
      });
    }
  }

  Future<void> _pickAudio() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.audio,
      allowMultiple: false,
    );
    if (result != null && result.files.single.path != null) {
      setState(() {
        _selectedAudio = File(result.files.single.path!);
      });
    }
  }

  Future<void> _pickVideo() async {
    final picked = await _imagePicker.pickVideo(source: ImageSource.gallery);
    if (picked != null) {
      setState(() {
        _selectedVideo = File(picked.path);
      });
    }
  }

  void _startDetection() {
    final message = _messageController.text.trim();
    final hasFiles = _selectedImage != null ||
                     _selectedAudio != null ||
                     _selectedVideo != null;

    if (message.isEmpty && !hasFiles) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请输入内容或选择文件')),
      );
      return;
    }

    // 大文件使用异步检测
    final isLargeFile = _selectedVideo != null ||
                        (_selectedAudio != null &&
                         _selectedAudio!.lengthSync() > 5 * 1024 * 1024);

    final bloc = context.read<DetectionBloc>();

    if (isLargeFile) {
      bloc.add(StartAsyncDetection(
        message: message,
        audioFile: _selectedAudio,
        imageFile: _selectedImage,
        videoFile: _selectedVideo,
      ));
    } else {
      bloc.add(StartDetection(
        message: message,
        audioFile: _selectedAudio,
        imageFile: _selectedImage,
        videoFile: _selectedVideo,
      ));
    }

    // 清除输入
    _messageController.clear();
    setState(() {
      _selectedImage = null;
      _selectedAudio = null;
      _selectedVideo = null;
    });
  }
}

/// 快捷操作 Chip
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
      avatar: Icon(icon, size: 18, color: Colors.white70),
      label: Text(label),
      labelStyle: const TextStyle(color: Colors.white70, fontSize: 13),
      backgroundColor: Colors.white.withOpacity(0.05),
      side: BorderSide(color: Colors.white.withOpacity(0.1)),
      onPressed: onTap,
    );
  }
}

/// 文件 Chip
class _FileChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onDelete;

  const _FileChip({
    required this.icon,
    required this.label,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    return Chip(
      avatar: Icon(icon, size: 16, color: AppTheme.primaryColor),
      label: Text(label),
      labelStyle: const TextStyle(color: Colors.white, fontSize: 12),
      backgroundColor: AppTheme.primaryColor.withOpacity(0.1),
      deleteIcon: const Icon(Icons.close, size: 16, color: Colors.white60),
      onDeleted: onDelete,
    );
  }
}

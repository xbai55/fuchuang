import 'package:flutter/material.dart';
import 'dart:math' as math;
import '../../../data/models/detection_result.dart';
import '../../theme/app_theme.dart';
import '../../widgets/markdown_text.dart';

/// 检测结果页面
/// 展示 AI 分析结果，高风险时带有红色呼吸灯效果
class ResultPage extends StatefulWidget {
  final DetectionResult result;

  const ResultPage({
    super.key,
    required this.result,
  });

  @override
  State<ResultPage> createState() => _ResultPageState();
}

class _ResultPageState extends State<ResultPage> with TickerProviderStateMixin {
  late AnimationController _breathingController;
  late Animation<double> _breathingAnimation;

  @override
  void initState() {
    super.initState();

    // 呼吸灯动画控制器
    _breathingController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2000),
    );

    _breathingAnimation = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _breathingController,
      curve: Curves.easeInOut,
    ));

    // 高风险时启动呼吸灯
    if (widget.result.isHighRisk) {
      _breathingController.repeat(reverse: true);
    }
  }

  @override
  void dispose() {
    _breathingController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.backgroundColor,
      body: AnimatedBuilder(
        animation: _breathingAnimation,
        builder: (context, child) {
          // 高风险时背景红色呼吸效果
          final backgroundColor = widget.result.isHighRisk
              ? Color.lerp(
                  AppTheme.backgroundColor,
                  Colors.red.withValues(alpha: 0.15),
                  _breathingAnimation.value * 0.5,
                )
              : AppTheme.backgroundColor;

          return Container(
            decoration: BoxDecoration(
              color: backgroundColor,
            ),
            child: SafeArea(
              child: Column(
                children: [
                  _buildAppBar(),
                  Expanded(
                    child: SingleChildScrollView(
                      padding: const EdgeInsets.all(24.0),
                      child: Column(
                        children: [
                          _buildRiskIndicator(),
                          const SizedBox(height: 32),
                          _buildWarningCard(),
                          const SizedBox(height: 24),
                          _buildDetailCard(),
                        ],
                      ),
                    ),
                  ),
                  _buildBottomActions(),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildAppBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(8, 8, 16, 8),
      child: Row(
        children: [
          IconButton(
            icon: const Icon(Icons.arrow_back, color: Colors.white),
            onPressed: () => Navigator.pop(context),
          ),
          const Expanded(
            child: Text(
              '检测结果',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          const SizedBox(width: 48), // 平衡布局
        ],
      ),
    );
  }

  Widget _buildRiskIndicator() {
    final color = _getRiskColor();
    final icon = _getRiskIcon();
    final title = widget.result.riskLevelText;
    final subtitle = widget.result.scamType.isNotEmpty
        ? '疑似${widget.result.scamType}'
        : '未知诈骗类型';

    return Column(
      children: [
        // 风险分数环形指示器
        Stack(
          alignment: Alignment.center,
          children: [
            // 外圈呼吸光晕（仅高风险）
            if (widget.result.isHighRisk)
              AnimatedBuilder(
                animation: _breathingAnimation,
                builder: (context, child) {
                  return Container(
                    width: 180 + _breathingAnimation.value * 20,
                    height: 180 + _breathingAnimation.value * 20,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: Colors.red.withValues(
                        alpha: 0.1 + _breathingAnimation.value * 0.2,
                      ),
                    ),
                  );
                },
              ),

            // 主环形进度
            SizedBox(
              width: 160,
              height: 160,
              child: TweenAnimationBuilder<double>(
                tween: Tween(begin: 0, end: widget.result.riskScore / 100),
                duration: const Duration(milliseconds: 1500),
                curve: Curves.easeOutCubic,
                builder: (context, value, child) {
                  return CustomPaint(
                    painter: _RiskRingPainter(
                      progress: value,
                      color: color,
                      strokeWidth: 12,
                    ),
                    child: Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(icon, color: color, size: 40),
                          const SizedBox(height: 8),
                          Text(
                            '${widget.result.riskScore}',
                            style: TextStyle(
                              color: color,
                              fontSize: 42,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          Text(
                            '风险分',
                            style: TextStyle(
                              color: color.withValues(alpha: 0.7),
                              fontSize: 12,
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
          ],
        ),

        const SizedBox(height: 24),

        // 风险等级标签
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: color.withValues(alpha: 0.5), width: 2),
          ),
          child: Text(
            title,
            style: TextStyle(
              color: color,
              fontSize: 20,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),

        const SizedBox(height: 12),

        // 诈骗类型
        Text(
          subtitle,
          style: const TextStyle(
            color: Colors.white70,
            fontSize: 16,
          ),
        ),

        // 高风险警告动画
        if (widget.result.isHighRisk)
          Padding(
            padding: const EdgeInsets.only(top: 16),
            child: AnimatedBuilder(
              animation: _breathingAnimation,
              builder: (context, child) {
                return Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      Icons.warning_rounded,
                      color: Colors.red.withValues(
                        alpha: 0.7 + _breathingAnimation.value * 0.3,
                      ),
                      size: 24,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      '⚠️ 高危诈骗警告',
                      style: TextStyle(
                        color: Colors.red.withValues(
                          alpha: 0.8 + _breathingAnimation.value * 0.2,
                        ),
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                );
              },
            ),
          ),
      ],
    );
  }

  Widget _buildWarningCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            _getRiskColor().withValues(alpha: 0.2),
            _getRiskColor().withValues(alpha: 0.05),
          ],
        ),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: _getRiskColor().withValues(alpha: 0.3),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.info_outline, color: _getRiskColor(), size: 20),
              const SizedBox(width: 8),
              Text(
                'AI 分析结果',
                style: TextStyle(
                  color: _getRiskColor(),
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          MarkdownText(
            widget.result.warningMessage,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 15,
              height: 1.6,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDetailCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.outlineColor),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.description_outlined, color: Colors.white60, size: 20),
              SizedBox(width: 8),
              Text(
                '详细报告',
                style: TextStyle(
                  color: Colors.white60,
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          MarkdownText(
            widget.result.finalReport,
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.8),
              fontSize: 14,
              height: 1.6,
            ),
          ),
          if (widget.result.guardianAlert) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.red.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.red.withValues(alpha: 0.3)),
              ),
              child: const Row(
                children: [
                  Icon(Icons.notification_important, color: Colors.red),
                  SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '系统已自动通知您的监护人',
                      style: TextStyle(color: Colors.red),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildBottomActions() {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.bottomCenter,
          end: Alignment.topCenter,
          colors: [
            AppTheme.backgroundColor,
            AppTheme.backgroundColor.withValues(alpha: 0),
          ],
        ),
      ),
      child: Row(
        children: [
          Expanded(
            child: OutlinedButton.icon(
              onPressed: () {
                // 分享功能
              },
              icon: const Icon(Icons.share_outlined),
              label: const Text('分享'),
              style: OutlinedButton.styleFrom(
                foregroundColor: Colors.white70,
                side: BorderSide(color: Colors.white.withValues(alpha: 0.3)),
                padding: const EdgeInsets.symmetric(vertical: 16),
              ),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: ElevatedButton.icon(
              onPressed: () => Navigator.pop(context),
              icon: const Icon(Icons.check),
              label: const Text('我已了解'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryColor,
                foregroundColor: const Color(0xFF04201C),
                padding: const EdgeInsets.symmetric(vertical: 16),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Color _getRiskColor() {
    switch (widget.result.riskLevel) {
      case 'high':
        return AppTheme.errorColor;
      case 'medium':
        return AppTheme.warningColor;
      case 'low':
        return AppTheme.successColor;
      default:
        return Colors.grey;
    }
  }

  IconData _getRiskIcon() {
    switch (widget.result.riskLevel) {
      case 'high':
        return Icons.dangerous_rounded;
      case 'medium':
        return Icons.warning_amber_rounded;
      case 'low':
        return Icons.check_circle_outline;
      default:
        return Icons.help_outline;
    }
  }
}

/// 风险环形进度绘制器
class _RiskRingPainter extends CustomPainter {
  final double progress;
  final Color color;
  final double strokeWidth;

  _RiskRingPainter({
    required this.progress,
    required this.color,
    required this.strokeWidth,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = (size.width - strokeWidth) / 2;

    // 背景圆环
    final bgPaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.1)
      ..strokeWidth = strokeWidth
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    canvas.drawCircle(center, radius, bgPaint);

    // 进度圆环
    final progressPaint = Paint()
      ..color = color
      ..strokeWidth = strokeWidth
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..shader = SweepGradient(
        colors: [color, color.withValues(alpha: 0.5)],
        startAngle: -math.pi / 2,
        endAngle: -math.pi / 2 + 2 * math.pi * progress,
      ).createShader(
        Rect.fromCircle(center: center, radius: radius),
      );

    const startAngle = -math.pi / 2;
    final sweepAngle = 2 * math.pi * progress;

    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      startAngle,
      sweepAngle,
      false,
      progressPaint,
    );
  }

  @override
  bool shouldRepaint(covariant _RiskRingPainter oldDelegate) {
    return oldDelegate.progress != progress ||
        oldDelegate.color != color ||
        oldDelegate.strokeWidth != strokeWidth;
  }
}

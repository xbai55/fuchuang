part of 'detection_bloc.dart';

/// 检测状态
abstract class DetectionState {}

/// 初始状态
class DetectionInitial extends DetectionState {}

/// 检测中
class Detecting extends DetectionState {
  final String message;
  final int progress;
  final bool isAsync;

  Detecting({
    required this.message,
    required this.progress,
    required this.isAsync,
  });

  Detecting copyWith({
    String? message,
    int? progress,
    bool? isAsync,
  }) {
    return Detecting(
      message: message ?? this.message,
      progress: progress ?? this.progress,
      isAsync: isAsync ?? this.isAsync,
    );
  }
}

/// 检测成功
class DetectionSuccess extends DetectionState {
  final DetectionResult result;

  DetectionSuccess(this.result);
}

/// 检测失败
class DetectionError extends DetectionState {
  final String error;

  DetectionError(this.error);
}

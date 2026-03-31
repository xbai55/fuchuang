part of 'detection_bloc.dart';

/// 检测事件
abstract class DetectionEvent {}

/// 开始同步检测
class StartDetection extends DetectionEvent {
  final String message;
  final File? audioFile;
  final File? imageFile;
  final File? videoFile;

  StartDetection({
    required this.message,
    this.audioFile,
    this.imageFile,
    this.videoFile,
  });
}

/// 开始异步检测（适合大文件）
class StartAsyncDetection extends DetectionEvent {
  final String message;
  final File? audioFile;
  final File? imageFile;
  final File? videoFile;

  StartAsyncDetection({
    required this.message,
    this.audioFile,
    this.imageFile,
    this.videoFile,
  });
}

/// 更新进度
class UpdateProgress extends DetectionEvent {
  final int progress;

  UpdateProgress(this.progress);
}

/// 检测完成
class DetectionCompleted extends DetectionEvent {
  final DetectionResult result;

  DetectionCompleted(this.result);
}

/// 检测失败
class DetectionFailed extends DetectionEvent {
  final String error;

  DetectionFailed(this.error);
}

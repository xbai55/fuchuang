import 'dart:io';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../data/api/fraud_api.dart';
import '../../../data/models/detection_result.dart';

part 'detection_event.dart';
part 'detection_state.dart';

/// 检测 BLoC
class DetectionBloc extends Bloc<DetectionEvent, DetectionState> {
  final FraudApi _fraudApi = FraudApi();

  DetectionBloc() : super(DetectionInitial()) {
    on<StartDetection>(_onStartDetection);
    on<StartAsyncDetection>(_onStartAsyncDetection);
    on<UpdateProgress>(_onUpdateProgress);
    on<DetectionCompleted>(_onDetectionCompleted);
    on<DetectionFailed>(_onDetectionFailed);
  }

  /// 同步检测
  Future<void> _onStartDetection(
    StartDetection event,
    Emitter<DetectionState> emit,
  ) async {
    emit(Detecting(
      message: event.message,
      progress: 0,
      isAsync: false,
    ));

    try {
      final result = await _fraudApi.detect(
        message: event.message,
        audioFile: event.audioFile,
        imageFile: event.imageFile,
        videoFile: event.videoFile,
        onProgress: (sent, total) {
          if (total > 0) {
            final progress = (sent / total * 100).toInt();
            add(UpdateProgress(progress));
          }
        },
      );

      add(DetectionCompleted(result));
    } catch (e) {
      add(DetectionFailed(e.toString()));
    }
  }

  /// 异步检测
  Future<void> _onStartAsyncDetection(
    StartAsyncDetection event,
    Emitter<DetectionState> emit,
  ) async {
    emit(Detecting(
      message: event.message,
      progress: 0,
      isAsync: true,
    ));

    try {
      // 1. 创建异步任务
      final taskId = await _fraudApi.detectAsync(
        message: event.message,
        audioFile: event.audioFile,
        imageFile: event.imageFile,
        videoFile: event.videoFile,
        onProgress: (sent, total) {
          if (total > 0) {
            final progress = (sent / total * 50).toInt(); // 上传占50%
            add(UpdateProgress(progress));
          }
        },
      );

      // 2. 轮询任务状态
      await for (final result in _fraudApi.pollTaskStatus(taskId)) {
        add(UpdateProgress(100));
        add(DetectionCompleted(result));
        return;
      }
    } catch (e) {
      add(DetectionFailed(e.toString()));
    }
  }

  void _onUpdateProgress(
    UpdateProgress event,
    Emitter<DetectionState> emit,
  ) {
    if (state is Detecting) {
      final current = state as Detecting;
      emit(current.copyWith(progress: event.progress));
    }
  }

  void _onDetectionCompleted(
    DetectionCompleted event,
    Emitter<DetectionState> emit,
  ) {
    emit(DetectionSuccess(event.result));
  }

  void _onDetectionFailed(
    DetectionFailed event,
    Emitter<DetectionState> emit,
  ) {
    emit(DetectionError(event.error));
  }
}

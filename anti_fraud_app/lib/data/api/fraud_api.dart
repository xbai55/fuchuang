import 'dart:io';

import 'package:dio/dio.dart';

import '../../core/constants/api_constants.dart';
import '../../core/network/api_client.dart';
import '../../core/utils/media_compressor.dart';
import '../models/detection_result.dart';

/// 反诈检测 API
class FraudApi {
  final ApiClient _client = ApiClient();

  /// 同步检测（适合小文件）
  Future<DetectionResult> detect({
    required String message,
    File? audioFile,
    File? imageFile,
    File? videoFile,
    ProgressCallback? onProgress,
  }) async {
    // 构建表单数据
    final formData = FormData();
    formData.fields.add(MapEntry('message', message));

    // 添加文件（先压缩）
    if (imageFile != null) {
      final compressed = await MediaCompressor.compress(imageFile);
      formData.files.add(MapEntry(
        'image_file',
        await MultipartFile.fromFile(
          compressed.path,
          filename: 'image.jpg',
        ),
      ));
    }

    if (audioFile != null) {
      formData.files.add(MapEntry(
        'audio_file',
        await MultipartFile.fromFile(
          audioFile.path,
          filename: 'audio.mp3',
        ),
      ));
    }

    if (videoFile != null) {
      final compressed = await MediaCompressor.compress(videoFile);
      formData.files.add(MapEntry(
        'video_file',
        await MultipartFile.fromFile(
          compressed.path,
          filename: 'video.mp4',
        ),
      ));
    }

    final response = await _client.postForm<Map<String, dynamic>>(
      ApiConstants.fraudDetect,
      formData: formData,
      onSendProgress: onProgress,
    );

    return DetectionResult.fromJson(response!);
  }

  /// 异步检测（适合大文件）
  Future<String> detectAsync({
    required String message,
    File? audioFile,
    File? imageFile,
    File? videoFile,
    ProgressCallback? onProgress,
  }) async {
    final formData = FormData();
    formData.fields.add(MapEntry('message', message));

    if (imageFile != null) {
      final compressed = await MediaCompressor.compress(imageFile);
      formData.files.add(MapEntry(
        'image_file',
        await MultipartFile.fromFile(compressed.path, filename: 'image.jpg'),
      ));
    }

    if (audioFile != null) {
      formData.files.add(MapEntry(
        'audio_file',
        await MultipartFile.fromFile(audioFile.path, filename: 'audio.mp3'),
      ));
    }

    if (videoFile != null) {
      final compressed = await MediaCompressor.compress(videoFile);
      formData.files.add(MapEntry(
        'video_file',
        await MultipartFile.fromFile(compressed.path, filename: 'video.mp4'),
      ));
    }

    final response = await _client.postForm<Map<String, dynamic>>(
      ApiConstants.fraudDetectAsync,
      formData: formData,
      onSendProgress: onProgress,
    );

    return response!['task_id'] as String;
  }

  /// 轮询任务状态
  Stream<DetectionResult> pollTaskStatus(String taskId) async* {
    await for (final status in _client.pollTaskStatus(taskId)) {
      if (status.isCompleted && status.result != null) {
        yield DetectionResult.fromJson(status.result!);
      } else if (status.isFailed) {
        throw Exception(status.error ?? '检测失败');
      }
    }
  }

  /// 获取历史记录
  Future<PaginatedHistory> getHistory({int page = 1, int size = 20}) async {
    final response = await _client.get<Map<String, dynamic>>(
      ApiConstants.history,
      queryParameters: {'page': page, 'size': size},
    );

    final data = response!['data'] as Map<String, dynamic>;
    return PaginatedHistory.fromJson(data);
  }
}

/// 分页历史记录
class PaginatedHistory {
  final List<DetectionHistory> items;
  final int total;
  final int page;
  final int size;
  final int pages;
  final bool hasNext;
  final bool hasPrev;

  PaginatedHistory({
    required this.items,
    required this.total,
    required this.page,
    required this.size,
    required this.pages,
    required this.hasNext,
    required this.hasPrev,
  });

  factory PaginatedHistory.fromJson(Map<String, dynamic> json) {
    return PaginatedHistory(
      items: (json['items'] as List)
          .map((e) => DetectionHistory.fromJson(e as Map<String, dynamic>))
          .toList(),
      total: json['total'] as int,
      page: json['page'] as int,
      size: json['size'] as int,
      pages: json['pages'] as int,
      hasNext: json['has_next'] as bool,
      hasPrev: json['has_prev'] as bool,
    );
  }
}

/// 检测历史
class DetectionHistory {
  final int id;
  final String userMessage;
  final String botResponse;
  final int riskScore;
  final String riskLevel;
  final String scamType;
  final bool guardianAlert;
  final DateTime createdAt;

  DetectionHistory({
    required this.id,
    required this.userMessage,
    required this.botResponse,
    required this.riskScore,
    required this.riskLevel,
    required this.scamType,
    required this.guardianAlert,
    required this.createdAt,
  });

  factory DetectionHistory.fromJson(Map<String, dynamic> json) {
    return DetectionHistory(
      id: json['id'] as int,
      userMessage: json['user_message'] as String,
      botResponse: json['bot_response'] as String,
      riskScore: json['risk_score'] as int,
      riskLevel: json['risk_level'] as String,
      scamType: json['scam_type'] as String,
      guardianAlert: json['guardian_alert'] as bool,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}

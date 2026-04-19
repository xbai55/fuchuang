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
    await _client.ensureAuthenticated();

    // 构建表单数据
    final formData = FormData();
    formData.fields.add(MapEntry('message', message));
    formData.fields.add(MapEntry(
      'client_request_started_at_ms',
      DateTime.now().millisecondsSinceEpoch.toString(),
    ));

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
    await _client.ensureAuthenticated();

    final formData = FormData();
    formData.fields.add(MapEntry('message', message));
    formData.fields.add(MapEntry(
      'client_request_started_at_ms',
      DateTime.now().millisecondsSinceEpoch.toString(),
    ));

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
    await _client.ensureAuthenticated();

    final response = await _client.get<Map<String, dynamic>>(
      ApiConstants.history,
      queryParameters: {'page': page, 'size': size},
    );

    return PaginatedHistory.fromJson(response!);
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
    final rawItems = json['items'];
    return PaginatedHistory(
      items: (rawItems is List ? rawItems : const [])
          .whereType<Map<String, dynamic>>()
          .map(DetectionHistory.fromJson)
          .toList(),
      total: (json['total'] as num?)?.toInt() ?? 0,
      page: (json['page'] as num?)?.toInt() ?? 1,
      size: (json['size'] as num?)?.toInt() ?? 20,
      pages: (json['pages'] as num?)?.toInt() ?? 1,
      hasNext: json['has_next'] as bool? ?? false,
      hasPrev: json['has_prev'] as bool? ?? false,
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
  final String chatMode;
  final bool guardianAlert;
  final DateTime createdAt;

  DetectionHistory({
    required this.id,
    required this.userMessage,
    required this.botResponse,
    required this.riskScore,
    required this.riskLevel,
    required this.scamType,
    required this.chatMode,
    required this.guardianAlert,
    required this.createdAt,
  });

  factory DetectionHistory.fromJson(Map<String, dynamic> json) {
    final createdAtText = json['created_at'] as String?;
    return DetectionHistory(
      id: (json['id'] as num?)?.toInt() ?? 0,
      userMessage: json['user_message'] as String? ?? '',
      botResponse: json['bot_response'] as String? ?? '',
      riskScore: (json['risk_score'] as num?)?.toInt() ?? 0,
      riskLevel: json['risk_level'] as String? ?? 'low',
      scamType: json['scam_type'] as String? ?? '',
      chatMode: json['chat_mode'] as String? ?? 'fraud',
      guardianAlert: json['guardian_alert'] as bool? ?? false,
      createdAt: createdAtText == null
          ? DateTime.now()
          : DateTime.tryParse(createdAtText) ?? DateTime.now(),
    );
  }
}

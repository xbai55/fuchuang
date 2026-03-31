import 'package:json_annotation/json_annotation.dart';

part 'api_response.g.dart';

/// 统一 API 响应模型
@JsonSerializable(genericArgumentFactories: true)
class ApiResponse<T> {
  final int code;
  final String message;
  final T? data;
  final int timestamp;
  final String? requestId;

  ApiResponse({
    required this.code,
    required this.message,
    this.data,
    required this.timestamp,
    this.requestId,
  });

  /// 是否成功
  bool get isSuccess => code == 200;

  factory ApiResponse.fromJson(
    Map<String, dynamic> json,
    T Function(Object? json) fromJsonT,
  ) =>
      _$ApiResponseFromJson(json, fromJsonT);

  Map<String, dynamic> toJson(Object? Function(T value) toJsonT) =>
      _$ApiResponseToJson(this, toJsonT);
}

/// 分页数据模型
@JsonSerializable(genericArgumentFactories: true)
class PaginationData<T> {
  final List<T> items;
  final int total;
  final int page;
  final int size;
  final int pages;
  final bool hasNext;
  final bool hasPrev;

  PaginationData({
    required this.items,
    required this.total,
    required this.page,
    required this.size,
    required this.pages,
    required this.hasNext,
    required this.hasPrev,
  });

  factory PaginationData.fromJson(
    Map<String, dynamic> json,
    T Function(Object? json) fromJsonT,
  ) =>
      _$PaginationDataFromJson(json, fromJsonT);

  Map<String, dynamic> toJson(Object? Function(T value) toJsonT) =>
      _$PaginationDataToJson(this, toJsonT);
}

/// 异步任务响应
@JsonSerializable()
class AsyncTaskResponse {
  final String taskId;
  final String status;
  final int estimatedTime;
  final String pollUrl;

  AsyncTaskResponse({
    required this.taskId,
    required this.status,
    required this.estimatedTime,
    required this.pollUrl,
  });

  factory AsyncTaskResponse.fromJson(Map<String, dynamic> json) =>
      _$AsyncTaskResponseFromJson(json);

  Map<String, dynamic> toJson() => _$AsyncTaskResponseToJson(this);
}

/// 任务状态响应
@JsonSerializable()
class TaskStatusResponse {
  final String taskId;
  final String status;
  final int progress;
  final Map<String, dynamic>? result;
  final String? error;
  final double elapsedTime;
  final String? inputSummary;

  TaskStatusResponse({
    required this.taskId,
    required this.status,
    required this.progress,
    this.result,
    this.error,
    required this.elapsedTime,
    this.inputSummary,
  });

  bool get isCompleted => status == 'completed';
  bool get isFailed => status == 'failed';
  bool get isProcessing => status == 'processing';
  bool get isPending => status == 'pending';

  factory TaskStatusResponse.fromJson(Map<String, dynamic> json) =>
      _$TaskStatusResponseFromJson(json);

  Map<String, dynamic> toJson() => _$TaskStatusResponseToJson(this);
}

// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'api_response.dart';

ApiResponse<T> _$ApiResponseFromJson<T>(
  Map<String, dynamic> json,
  T Function(Object? json) fromJsonT,
) =>
    ApiResponse<T>(
      code: (json['code'] as num).toInt(),
      message: json['message'] as String,
      data: _$nullableGenericFromJson(json['data'], fromJsonT),
      timestamp: (json['timestamp'] as num).toInt(),
      requestId: json['requestId'] as String?,
    );

Map<String, dynamic> _$ApiResponseToJson<T>(
  ApiResponse<T> instance,
  Object? Function(T value) toJsonT,
) =>
    <String, dynamic>{
      'code': instance.code,
      'message': instance.message,
      'data': _$nullableGenericToJson(instance.data, toJsonT),
      'timestamp': instance.timestamp,
      'requestId': instance.requestId,
    };

PaginationData<T> _$PaginationDataFromJson<T>(
  Map<String, dynamic> json,
  T Function(Object? json) fromJsonT,
) =>
    PaginationData<T>(
      items: (json['items'] as List<dynamic>).map(fromJsonT).toList(),
      total: (json['total'] as num).toInt(),
      page: (json['page'] as num).toInt(),
      size: (json['size'] as num).toInt(),
      pages: (json['pages'] as num).toInt(),
      hasNext: json['hasNext'] as bool,
      hasPrev: json['hasPrev'] as bool,
    );

Map<String, dynamic> _$PaginationDataToJson<T>(
  PaginationData<T> instance,
  Object? Function(T value) toJsonT,
) =>
    <String, dynamic>{
      'items': instance.items.map(toJsonT).toList(),
      'total': instance.total,
      'page': instance.page,
      'size': instance.size,
      'pages': instance.pages,
      'hasNext': instance.hasNext,
      'hasPrev': instance.hasPrev,
    };

AsyncTaskResponse _$AsyncTaskResponseFromJson(Map<String, dynamic> json) =>
    AsyncTaskResponse(
      taskId: json['taskId'] as String,
      status: json['status'] as String,
      estimatedTime: (json['estimatedTime'] as num).toInt(),
      pollUrl: json['pollUrl'] as String,
    );

Map<String, dynamic> _$AsyncTaskResponseToJson(AsyncTaskResponse instance) =>
    <String, dynamic>{
      'taskId': instance.taskId,
      'status': instance.status,
      'estimatedTime': instance.estimatedTime,
      'pollUrl': instance.pollUrl,
    };

TaskStatusResponse _$TaskStatusResponseFromJson(Map<String, dynamic> json) =>
    TaskStatusResponse(
      taskId: json['taskId'] as String,
      status: json['status'] as String,
      progress: (json['progress'] as num).toInt(),
      result: json['result'] as Map<String, dynamic>?,
      error: json['error'] as String?,
      elapsedTime: (json['elapsedTime'] as num).toDouble(),
      inputSummary: json['inputSummary'] as String?,
    );

Map<String, dynamic> _$TaskStatusResponseToJson(TaskStatusResponse instance) =>
    <String, dynamic>{
      'taskId': instance.taskId,
      'status': instance.status,
      'progress': instance.progress,
      'result': instance.result,
      'error': instance.error,
      'elapsedTime': instance.elapsedTime,
      'inputSummary': instance.inputSummary,
    };

T? _$nullableGenericFromJson<T>(
  Object? input,
  T Function(Object? json) fromJson,
) =>
    input == null ? null : fromJson(input);

Object? _$nullableGenericToJson<T>(
  T? input,
  Object? Function(T value) toJson,
) =>
    input == null ? null : toJson(input);

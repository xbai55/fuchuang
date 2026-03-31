import 'dart:io';
import 'dart:typed_data';
import 'package:flutter_image_compress/flutter_image_compress.dart';
import 'package:video_compress/video_compress.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as path;

/// 媒体文件压缩工具
/// 用于在上传前压缩图片和视频，减少流量消耗
class MediaCompressor {
  MediaCompressor._();

  /// 压缩图片
  /// [file] 原始图片文件
  /// [maxWidth] 最大宽度（默认1080）
  /// [maxHeight] 最大高度（默认1080）
  /// [quality] 压缩质量 0-100（默认85）
  static Future<File> compressImage(
    File file, {
    int maxWidth = 1080,
    int maxHeight = 1080,
    int quality = 85,
  }) async {
    try {
      // 获取临时目录
      final tempDir = await getTemporaryDirectory();
      final targetPath = path.join(
        tempDir.path,
        'compressed_${DateTime.now().millisecondsSinceEpoch}.jpg',
      );

      // 压缩图片
      final result = await FlutterImageCompress.compressAndGetFile(
        file.absolute.path,
        targetPath,
        minWidth: maxWidth,
        minHeight: maxHeight,
        quality: quality,
        format: CompressFormat.jpeg,
      );

      if (result == null) {
        throw Exception('图片压缩失败');
      }

      // XFile 转 File
      final resultFile = File(result.path);

      // 打印压缩信息
      final originalSize = await file.length();
      final compressedSize = await resultFile.length();
      print('图片压缩: ${(originalSize / 1024).toStringAsFixed(2)}KB -> '
          '${(compressedSize / 1024).toStringAsFixed(2)}KB '
          '(${(compressedSize / originalSize * 100).toStringAsFixed(1)}%)');

      return resultFile;
    } catch (e) {
      print('图片压缩错误: $e');
      // 压缩失败返回原文件
      return file;
    }
  }

  /// 压缩视频
  /// [file] 原始视频文件
  /// [quality] 压缩质量（低/中/高）
  static Future<File> compressVideo(
    File file, {
    VideoQuality quality = VideoQuality.DefaultQuality,
  }) async {
    try {
      // 使用 video_compress 库压缩
      final info = await VideoCompress.compressVideo(
        file.path,
        quality: quality,
        deleteOrigin: false,  // 不删除原文件
      );

      if (info == null || info.file == null) {
        throw Exception('视频压缩失败');
      }

      // 打印压缩信息
      final originalSize = await file.length();
      final compressedSize = await info.file!.length();
      print('视频压缩: ${(originalSize / 1024 / 1024).toStringAsFixed(2)}MB -> '
          '${(compressedSize / 1024 / 1024).toStringAsFixed(2)}MB '
          '(${(compressedSize / originalSize * 100).toStringAsFixed(1)}%)');
      print('视频时长: ${info.duration}秒');

      return info.file!;
    } catch (e) {
      print('视频压缩错误: $e');
      // 压缩失败返回原文件
      return file;
    }
  }

  /// 获取压缩后的媒体文件
  /// 根据文件类型自动选择压缩方式
  static Future<File> compress(File file, {String? type}) async {
    final extension = path.extension(file.path).toLowerCase();
    final mimeType = type ?? _getMimeType(extension);

    if (mimeType.startsWith('image/')) {
      return await compressImage(file);
    } else if (mimeType.startsWith('video/')) {
      return await compressVideo(file);
    }

    // 其他类型不压缩
    return file;
  }

  /// 清理临时文件
  static Future<void> cleanTempFiles() async {
    try {
      final tempDir = await getTemporaryDirectory();
      final files = tempDir.listSync();

      for (var file in files) {
        if (file is File && file.path.contains('compressed_')) {
          await file.delete();
        }
      }

      print('临时文件清理完成');
    } catch (e) {
      print('清理临时文件失败: $e');
    }
  }

  /// 根据扩展名获取 MIME 类型
  static String _getMimeType(String extension) {
    switch (extension) {
      case '.jpg':
      case '.jpeg':
        return 'image/jpeg';
      case '.png':
        return 'image/png';
      case '.gif':
        return 'image/gif';
      case '.webp':
        return 'image/webp';
      case '.mp4':
        return 'video/mp4';
      case '.mov':
        return 'video/quicktime';
      case '.avi':
        return 'video/x-msvideo';
      case '.mp3':
        return 'audio/mpeg';
      case '.wav':
        return 'audio/wav';
      case '.m4a':
        return 'audio/mp4';
      default:
        return 'application/octet-stream';
    }
  }
}

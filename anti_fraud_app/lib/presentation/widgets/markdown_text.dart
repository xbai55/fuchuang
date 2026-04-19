import 'package:flutter/material.dart';

/// Lightweight markdown renderer for AI replies.
///
/// Supports the subset the backend commonly returns: bold spans, headings and
/// bullet/numbered lists. It keeps the UI readable without introducing a heavy
/// dependency for plain chat bubbles.
class MarkdownText extends StatelessWidget {
  final String data;
  final TextStyle? style;
  final TextStyle? boldStyle;
  final int? maxLines;
  final TextOverflow overflow;

  const MarkdownText(
    this.data, {
    super.key,
    this.style,
    this.boldStyle,
    this.maxLines,
    this.overflow = TextOverflow.clip,
  });

  @override
  Widget build(BuildContext context) {
    final baseStyle = style ?? DefaultTextStyle.of(context).style;
    final strongStyle = boldStyle ??
        baseStyle.copyWith(
          fontWeight: FontWeight.w800,
          color: baseStyle.color,
        );

    if (!data.contains('\n')) {
      return RichText(
        maxLines: maxLines,
        overflow: overflow,
        text: TextSpan(
          style: baseStyle,
          children: _parseInline(data, baseStyle, strongStyle),
        ),
      );
    }

    final lines = data.replaceAll('\r\n', '\n').split('\n');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final rawLine in lines)
          _buildLine(rawLine, baseStyle, strongStyle),
      ],
    );
  }

  Widget _buildLine(
    String rawLine,
    TextStyle baseStyle,
    TextStyle strongStyle,
  ) {
    final line = rawLine.trimRight();
    if (line.trim().isEmpty) {
      return const SizedBox(height: 8);
    }

    final headingMatch = RegExp(r'^(#{1,6})\s+(.+)$').firstMatch(line);
    if (headingMatch != null) {
      final level = headingMatch.group(1)!.length;
      final text = headingMatch.group(2)!;
      final headingStyle = strongStyle.copyWith(
        fontSize: (baseStyle.fontSize ?? 14) + (7 - level).clamp(1, 4),
      );
      return Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: RichText(
          text: TextSpan(
            style: headingStyle,
            children: _parseInline(text, headingStyle, headingStyle),
          ),
        ),
      );
    }

    final bulletMatch = RegExp(r'^[-*]\s+(.+)$').firstMatch(line.trimLeft());
    if (bulletMatch != null) {
      return _buildListLine(
        marker: '•',
        text: bulletMatch.group(1)!,
        baseStyle: baseStyle,
        strongStyle: strongStyle,
      );
    }

    final numberedMatch =
        RegExp(r'^(\d+[.)])\s+(.+)$').firstMatch(line.trimLeft());
    if (numberedMatch != null) {
      return _buildListLine(
        marker: numberedMatch.group(1)!,
        text: numberedMatch.group(2)!,
        baseStyle: baseStyle,
        strongStyle: strongStyle,
      );
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: RichText(
        text: TextSpan(
          style: baseStyle,
          children: _parseInline(line, baseStyle, strongStyle),
        ),
      ),
    );
  }

  Widget _buildListLine({
    required String marker,
    required String text,
    required TextStyle baseStyle,
    required TextStyle strongStyle,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: marker == '•' ? 16 : 28,
            child: Text(marker, style: baseStyle),
          ),
          Expanded(
            child: RichText(
              text: TextSpan(
                style: baseStyle,
                children: _parseInline(text, baseStyle, strongStyle),
              ),
            ),
          ),
        ],
      ),
    );
  }

  List<TextSpan> _parseInline(
    String text,
    TextStyle baseStyle,
    TextStyle strongStyle,
  ) {
    final spans = <TextSpan>[];
    final regex = RegExp(r'\*\*(.+?)\*\*');
    var cursor = 0;

    for (final match in regex.allMatches(text)) {
      if (match.start > cursor) {
        spans.add(TextSpan(text: text.substring(cursor, match.start)));
      }
      spans.add(TextSpan(text: match.group(1), style: strongStyle));
      cursor = match.end;
    }

    if (cursor < text.length) {
      spans.add(TextSpan(text: text.substring(cursor)));
    }

    return spans.isEmpty ? [TextSpan(text: text, style: baseStyle)] : spans;
  }
}

String cleanMarkdownText(String text) {
  return text
      .replaceAllMapped(
          RegExp(r'\*\*(.+?)\*\*'), (match) => match.group(1) ?? '')
      .replaceAll(RegExp(r'(^|\n)#{1,6}\s+'), '\n')
      .replaceAll(RegExp(r'(^|\n)[-*]\s+'), '\n')
      .trim();
}

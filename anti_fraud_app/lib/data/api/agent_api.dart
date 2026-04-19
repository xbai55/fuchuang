import '../../core/constants/api_constants.dart';
import '../../core/network/api_client.dart';

/// 反诈助手对话 API
class AgentApi {
  final ApiClient _client = ApiClient();

  Future<AgentChatResponse> chat({
    required String message,
    String? conversationId,
  }) async {
    await _client.ensureAuthenticated();

    final response = await _client.post<Map<String, dynamic>>(
      ApiConstants.agentChat,
      data: {
        'message': message,
        if (conversationId != null) 'conversation_id': conversationId,
        'context': {
          'client': 'flutter_mobile',
          'scene': 'anti_fraud_assistant',
        },
      },
    );

    return AgentChatResponse.fromJson(response ?? const {});
  }
}

class AgentChatResponse {
  final String message;
  final List<String> suggestions;
  final List<Map<String, dynamic>> toolCalls;
  final String conversationId;

  const AgentChatResponse({
    required this.message,
    required this.suggestions,
    required this.toolCalls,
    required this.conversationId,
  });

  factory AgentChatResponse.fromJson(Map<String, dynamic> json) {
    final rawSuggestions = json['suggestions'];
    final rawToolCalls = json['tool_calls'];

    return AgentChatResponse(
      message: json['message'] as String? ?? '',
      suggestions: rawSuggestions is List
          ? rawSuggestions.map((item) => item.toString()).toList()
          : const [],
      toolCalls: rawToolCalls is List
          ? rawToolCalls
              .whereType<Map<String, dynamic>>()
              .map((item) => Map<String, dynamic>.from(item))
              .toList()
          : const [],
      conversationId: json['conversation_id'] as String? ?? '',
    );
  }
}

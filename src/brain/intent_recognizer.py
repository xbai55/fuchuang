"""
Intent recognizer for the anti-fraud workflow.
Builds a lightweight user profile snapshot and short-term memory summary.
"""
from typing import Any, Dict

from src.core.models import GlobalState
from src.evolution.runtime import get_evolution_runtime


class IntentRecognizer:
    """Heuristic intent recognizer with short-term memory support."""

    KEYWORD_RULES = {
        "seek_help": ["怎么办", "被骗", "诈骗", "求助", "怎么办啊", "救命"],
        "verify_message": ["是真的吗", "真实吗", "能不能信", "可信", "链接", "验证码", "转账"],
        "report_fraud": ["报警", "举报", "投诉", "报案", "维权"],
        "guardian_contact": ["家人", "监护人", "联系人", "通知", "帮我联系"],
        "knowledge_query": ["是什么", "为什么", "案例", "科普", "解释一下"],
    }

    def __init__(self):
        self.runtime = get_evolution_runtime()

    async def analyze(self, state: GlobalState) -> Dict[str, Any]:
        """Analyze user intent and construct memory/profile metadata."""
        text = (state.get_combined_text() or "").strip()
        intent = self._detect_intent(text)
        user_id = state.user_context.user_id or "anonymous"

        recent_detections = self.runtime.get_recent_detections(user_id=user_id, limit=3)
        short_term_memory = self.runtime.build_short_term_memory(
            user_id=user_id,
            current_text=text,
            recent_detections=recent_detections,
        )

        profile_snapshot = {
            "user_id": user_id,
            "user_role": state.user_context.user_role.value,
            "has_guardian": bool(state.user_context.guardian_name or state.user_context.guardian_phone),
            "emergency_contact_count": len(state.user_context.emergency_contacts),
            "recent_detection_count": len(recent_detections),
            "intent": intent,
        }

        metadata = dict(state.workflow_metadata)
        metadata.update(
            {
                "profile_snapshot": profile_snapshot,
                "recent_detections": recent_detections,
            }
        )

        return {
            "intent": intent,
            "short_term_memory_summary": short_term_memory,
            "workflow_metadata": metadata,
        }

    def _detect_intent(self, text: str) -> str:
        if not text:
            return "general_consultation"

        lowered = text.lower()
        for intent, keywords in self.KEYWORD_RULES.items():
            if any(keyword in lowered for keyword in keywords):
                return intent

        if "?" in text or "？" in text:
            return "knowledge_query"
        return "general_consultation"

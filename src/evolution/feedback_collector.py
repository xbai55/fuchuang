"""
Feedback collector for user feedback on detection results.
Improves the system based on user feedback.
"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class FeedbackType(str, Enum):
    """Types of user feedback."""
    CORRECT = "correct"          # Detection was correct
    FALSE_POSITIVE = "false_positive"  # False alarm
    FALSE_NEGATIVE = "false_negative"  # Missed fraud
    USEFUL = "useful"            # Information was useful
    NOT_USEFUL = "not_useful"    # Information was not useful


@dataclass
class UserFeedback:
    """Represents user feedback."""
    feedback_id: str
    user_id: str
    detection_id: str
    feedback_type: FeedbackType
    comment: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class FeedbackCollector:
    """
    Collects and manages user feedback.

    Tracks:
    - Detection accuracy feedback
    - Report usefulness feedback
    - User suggestions
    """

    def __init__(self):
        """Initialize feedback collector."""
        self._feedback_store: List[UserFeedback] = []
        self._detection_feedback: Dict[str, List[str]] = {}  # detection_id -> feedback_ids

    async def collect(
        self,
        user_id: str,
        detection_id: str,
        feedback_type: FeedbackType,
        comment: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Collect feedback from user.

        Args:
            user_id: User ID
            detection_id: Detection result ID
            feedback_type: Type of feedback
            comment: Optional comment
            metadata: Optional metadata

        Returns:
            Collection result
        """
        feedback = UserFeedback(
            feedback_id=f"fb_{datetime.now().strftime('%Y%m%d%H%M%S')}_{user_id}",
            user_id=user_id,
            detection_id=detection_id,
            feedback_type=feedback_type,
            comment=comment,
            timestamp=datetime.now(),
            metadata=metadata or {},
        )

        # Store feedback
        self._feedback_store.append(feedback)

        # Index by detection
        if detection_id not in self._detection_feedback:
            self._detection_feedback[detection_id] = []
        self._detection_feedback[detection_id].append(feedback.feedback_id)

        return {
            "success": True,
            "feedback_id": feedback.feedback_id,
            "timestamp": feedback.timestamp.isoformat(),
        }

    def get_feedback_for_detection(
        self,
        detection_id: str,
    ) -> List[UserFeedback]:
        """
        Get all feedback for a detection.

        Args:
            detection_id: Detection ID

        Returns:
            List of feedback entries
        """
        feedback_ids = self._detection_feedback.get(detection_id, [])
        return [
            fb for fb in self._feedback_store
            if fb.feedback_id in feedback_ids
        ]

    def get_feedback_stats(
        self,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get feedback statistics.

        Args:
            user_id: Optional user ID to filter by

        Returns:
            Statistics dictionary
        """
        feedback_list = self._feedback_store
        if user_id:
            feedback_list = [fb for fb in feedback_list if fb.user_id == user_id]

        total = len(feedback_list)
        if total == 0:
            return {"total": 0}

        type_counts = {}
        for fb in feedback_list:
            type_counts[fb.feedback_type.value] = type_counts.get(fb.feedback_type.value, 0) + 1

        return {
            "total": total,
            "type_distribution": type_counts,
            "accuracy_indicators": {
                "correct_rate": type_counts.get("correct", 0) / total,
                "false_positive_rate": type_counts.get("false_positive", 0) / total,
                "false_negative_rate": type_counts.get("false_negative", 0) / total,
            },
        }

    def get_recent_feedback(
        self,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get recent feedback entries.

        Args:
            limit: Maximum number of entries

        Returns:
            List of feedback entries
        """
        recent = self._feedback_store[-limit:]
        return [
            {
                "feedback_id": fb.feedback_id,
                "user_id": fb.user_id,
                "detection_id": fb.detection_id,
                "feedback_type": fb.feedback_type.value,
                "comment": fb.comment,
                "timestamp": fb.timestamp.isoformat(),
            }
            for fb in reversed(recent)
        ]

    def get_improvement_suggestions(self) -> List[str]:
        """
        Analyze feedback and generate improvement suggestions.

        Returns:
            List of suggestions
        """
        suggestions = []
        stats = self.get_feedback_stats()

        # Check for patterns
        accuracy = stats.get("accuracy_indicators", {})

        if accuracy.get("false_positive_rate", 0) > 0.2:
            suggestions.append("False positive rate is high. Consider adjusting risk thresholds.")

        if accuracy.get("false_negative_rate", 0) > 0.1:
            suggestions.append("False negative rate is high. Model may be missing fraud patterns.")

        if stats.get("type_distribution", {}).get("not_useful", 0) > 10:
            suggestions.append("Reports marked as 'not useful'. Consider improving report quality.")

        return suggestions

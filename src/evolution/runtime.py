"""
Runtime wiring for evolution components.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.evolution.case_ingestor import CaseIngestor
from src.evolution.feedback_collector import FeedbackCollector, FeedbackType


class EvolutionRuntime:
    """Singleton runtime that wires case ingestion and feedback collection."""

    def __init__(self):
        self.case_ingestor = CaseIngestor()
        self.feedback_collector = FeedbackCollector()
        self._recent_detections: Dict[str, List[Dict[str, Any]]] = {}
        self._detection_index: Dict[str, Dict[str, Any]] = {}

    async def record_detection(
        self,
        user_id: str,
        input_text: str,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        detection_id = result.get("detection_id") or f"det_{uuid4().hex[:12]}"
        timestamp = datetime.utcnow().isoformat()
        snapshot = {
            "detection_id": detection_id,
            "timestamp": timestamp,
            "risk_score": result.get("risk_score", 0),
            "risk_level": result.get("risk_level", "low"),
            "scam_type": result.get("scam_type", ""),
            "warning_message": result.get("warning_message", ""),
            "input_preview": (input_text or "")[:120],
        }

        self._detection_index[detection_id] = {
            **snapshot,
            "full_input": input_text or "",
            "result": result,
            "user_id": user_id,
        }

        bucket = self._recent_detections.setdefault(user_id, [])
        bucket.append(snapshot)
        if len(bucket) > 10:
            del bucket[:-10]

        if snapshot["risk_level"] == "high" or result.get("guardian_alert"):
            await self.case_ingestor.ingest_from_detection_result(
                user_id=user_id,
                risk_score=snapshot["risk_score"],
                scam_type=snapshot["scam_type"] or "high_risk_detection",
                content=input_text or result.get("final_report") or result.get("warning_message") or "",
                confirmed_fraud=snapshot["risk_level"] == "high",
            )

        return snapshot

    async def collect_feedback(
        self,
        user_id: str,
        detection_id: str,
        feedback_type: str,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_type = FeedbackType(feedback_type)
        result = await self.feedback_collector.collect(
            user_id=user_id,
            detection_id=detection_id,
            feedback_type=normalized_type,
            comment=comment,
            metadata=self._detection_index.get(detection_id, {}),
        )

        snapshot = self._detection_index.get(detection_id)
        if snapshot and normalized_type in {FeedbackType.CORRECT, FeedbackType.FALSE_NEGATIVE}:
            result["ingestion"] = await self.case_ingestor.ingest_from_detection_result(
                user_id=user_id,
                risk_score=snapshot.get("risk_score", 0),
                scam_type=snapshot.get("scam_type") or "feedback_case",
                content=snapshot.get("full_input") or snapshot.get("warning_message") or "",
                confirmed_fraud=normalized_type == FeedbackType.CORRECT,
            )

        result["feedback_stats"] = self.feedback_collector.get_feedback_stats(user_id=user_id)
        return result

    def get_recent_detections(self, user_id: str, limit: int = 3) -> List[Dict[str, Any]]:
        return list(self._recent_detections.get(user_id, []))[-limit:]

    def get_detection(self, detection_id: str) -> Optional[Dict[str, Any]]:
        return self._detection_index.get(detection_id)

    def build_short_term_memory(
        self,
        user_id: str,
        current_text: str = "",
        recent_detections: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        recent = recent_detections if recent_detections is not None else self.get_recent_detections(user_id)
        if not recent:
            return "No prior anti-fraud interaction has been recorded for this user."

        lines = []
        for item in recent[-3:]:
            lines.append(
                f"{item['timestamp']}: {item['risk_level']} risk ({item['risk_score']}/100)"
                f", type={item['scam_type'] or 'unknown'}, input={item['input_preview']}"
            )

        current_hint = f" Current message: {(current_text or '')[:80]}" if current_text else ""
        return "Recent detections: " + " | ".join(lines) + current_hint


_runtime: Optional[EvolutionRuntime] = None


def get_evolution_runtime() -> EvolutionRuntime:
    global _runtime
    if _runtime is None:
        _runtime = EvolutionRuntime()
    return _runtime

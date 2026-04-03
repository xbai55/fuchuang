"""
Graph client for backend API.
Provides a simplified interface to the anti-fraud workflow graph.
"""
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

current_file_path = Path(__file__).resolve()
project_root = current_file_path.parent.parent.parent
src_path = project_root / "src"
project_root_str = str(project_root.resolve())
src_path_str = str(src_path.resolve())
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)
if src_path_str not in sys.path:
    sys.path.insert(0, src_path_str)

from core.models import EmergencyContact, GlobalState, MediaFile, UserContext, UserRole
from evolution.runtime import get_evolution_runtime
from graphs.graph import get_main_graph


class GraphClient:
    """Client for invoking the anti-fraud graph from the backend."""

    def __init__(self):
        self.graph = None
        self.runtime = get_evolution_runtime()

    async def detect_fraud(
        self,
        text: str = None,
        audio_path: str = None,
        image_path: str = None,
        video_path: str = None,
        user_role: str = "general",
        guardian_name: str = None,
        guardian_phone: str = None,
        emergency_contacts: Optional[List[Dict[str, Any]]] = None,
        notify_enabled: bool = True,
        notify_guardian_alert: bool = True,
        user_id: str = None,
        history_profile: Optional[Dict[str, Any]] = None,
        workflow_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if self.graph is None:
            self.graph = get_main_graph()

        input_files = []
        if audio_path:
            input_files.append(MediaFile(type="audio", url=audio_path))
        if image_path:
            input_files.append(MediaFile(type="image", url=image_path))
        if video_path:
            input_files.append(MediaFile(type="video", url=video_path))

        contacts = [
            EmergencyContact(
                name=item.get("name", ""),
                phone=item.get("phone", ""),
                relationship=item.get("relationship", ""),
                is_guardian=bool(item.get("is_guardian", False)),
            )
            for item in (emergency_contacts or [])
        ]

        state = GlobalState(
            input_text=text,
            input_files=input_files,
            user_context=UserContext(
                user_role=UserRole(user_role),
                guardian_name=guardian_name,
                guardian_phone=guardian_phone,
                user_id=user_id,
                notify_enabled=notify_enabled,
                notify_guardian_alert=notify_guardian_alert,
                emergency_contacts=contacts,
            ),
            workflow_metadata={
                "history_profile": dict(history_profile or {}),
                **dict(workflow_options or {}),
            },
        )

        thread_id = user_id or f"thread_{uuid4().hex[:12]}"
        result = await self.graph.ainvoke(
            state,
            config={"configurable": {"thread_id": thread_id}},
        )

        formatted = self._format_response(result)
        snapshot = await self.runtime.record_detection(
            user_id=user_id or "anonymous",
            input_text=text or "",
            result=formatted,
        )
        formatted["detection_id"] = snapshot["detection_id"]
        return formatted

    def _format_response(self, state: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(state, dict):
            risk = state.get("risk_assessment")
            intervention = state.get("intervention")
            similar_cases = state.get("similar_cases", [])
            final_report = state.get("final_report", "")
            guardian_notification = state.get("guardian_notification")
            short_term_memory_summary = state.get("short_term_memory_summary", "")
            intent = state.get("intent")
        else:
            risk = getattr(state, "risk_assessment", None)
            intervention = getattr(state, "intervention", None)
            similar_cases = getattr(state, "similar_cases", []) or []
            final_report = getattr(state, "final_report", "") or ""
            guardian_notification = getattr(state, "guardian_notification", None)
            short_term_memory_summary = getattr(state, "short_term_memory_summary", "") or ""
            intent = getattr(state, "intent", None)

        risk_score = 0
        risk_level = "low"
        scam_type = ""
        risk_clues = []
        if risk:
            if isinstance(risk, dict):
                risk_score = risk.get("score", 0)
                level = risk.get("level", "low")
                risk_level = level.value if hasattr(level, "value") else str(level)
                scam_type = risk.get("scam_type", "")
                risk_clues = risk.get("clues", [])
            else:
                risk_score = getattr(risk, "score", 0)
                level = getattr(risk, "level", "low")
                risk_level = level.value if hasattr(level, "value") else str(level)
                scam_type = getattr(risk, "scam_type", "")
                risk_clues = getattr(risk, "clues", []) or []

        warning_message = ""
        guardian_alert = False
        alert_reason = ""
        action_items = []
        escalation_actions = []
        if intervention:
            if isinstance(intervention, dict):
                warning_message = intervention.get("warning_message", "")
                guardian_alert = intervention.get("guardian_alert", False)
                alert_reason = intervention.get("alert_reason", "")
                action_items = intervention.get("action_items", [])
                escalation_actions = intervention.get("escalation_actions", [])
            else:
                warning_message = getattr(intervention, "warning_message", "")
                guardian_alert = getattr(intervention, "guardian_alert", False)
                alert_reason = getattr(intervention, "alert_reason", "")
                action_items = getattr(intervention, "action_items", []) or []
                escalation_actions = getattr(intervention, "escalation_actions", []) or []

        formatted_cases = []
        for case in similar_cases[:3]:
            if isinstance(case, dict):
                formatted_cases.append({"title": case.get("title", ""), "content": case.get("content", "")[:200]})
            else:
                formatted_cases.append(
                    {
                        "title": getattr(case, "title", ""),
                        "content": (getattr(case, "content", "") or "")[:200],
                    }
                )

        if guardian_notification:
            if hasattr(guardian_notification, "model_dump"):
                guardian_notification = guardian_notification.model_dump()
        else:
            guardian_notification = None

        return {
            "detection_id": f"det_{uuid4().hex[:12]}",
            "intent": intent,
            "short_term_memory_summary": short_term_memory_summary,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "scam_type": scam_type,
            "risk_clues": risk_clues,
            "warning_message": warning_message,
            "guardian_alert": guardian_alert,
            "alert_reason": alert_reason,
            "action_items": action_items,
            "escalation_actions": escalation_actions,
            "guardian_notification": guardian_notification,
            "final_report": final_report,
            "similar_cases": formatted_cases,
        }


graph_client = GraphClient()

"""
Graph client for backend API.
Provides a simplified interface to the refactored graph.
"""
import asyncio
import sys
import os
from pathlib import Path
from typing import Any, Dict, Optional

# Add src to path - more robust approach
current_file_path = Path(__file__).resolve()
project_root = current_file_path.parent.parent.parent
src_path = project_root / "src"

# Convert to string and normalize path separators for Windows
src_path_str = str(src_path.resolve())

# Add to sys.path if not already present
if src_path_str not in sys.path:
    sys.path.insert(0, src_path_str)

from core.models import GlobalState, MediaFile, UserContext, UserRole
from graphs.graph import main_graph


class GraphClient:
    """
    Client for interacting with the anti-fraud graph.

    Simplifies graph invocation for the backend API.
    """

    def __init__(self):
        """Initialize graph client."""
        self.graph = main_graph

    async def detect_fraud(
        self,
        text: str = None,
        audio_path: str = None,
        image_path: str = None,
        video_path: str = None,
        user_role: str = "general",
        guardian_name: str = None,
        user_id: str = None,
    ) -> Dict[str, Any]:
        """
        Run fraud detection workflow.

        Args:
            text: Text input
            audio_path: Audio file path
            image_path: Image file path
            video_path: Video file path
            user_role: User role (elderly/student/finance/general)
            guardian_name: Guardian name
            user_id: User ID

        Returns:
            Detection result dict
        """
        # Build input files
        input_files = []

        if audio_path:
            input_files.append(MediaFile(type="audio", url=audio_path))

        if image_path:
            input_files.append(MediaFile(type="image", url=image_path))

        if video_path:
            input_files.append(MediaFile(type="video", url=video_path))

        # Build state
        state = GlobalState(
            input_text=text,
            input_files=input_files,
            user_context=UserContext(
                user_role=UserRole(user_role),
                guardian_name=guardian_name,
                user_id=user_id,
            ),
        )

        # Run graph using async API (ainvoke)
        result = await self.graph.ainvoke(state)

        # Format response
        return self._format_response(result)

    def _format_response(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format graph state as API response.

        Args:
            state: Final graph state (dict from ainvoke)

        Returns:
            Response dict
        """
        # Handle dict return from ainvoke
        if isinstance(state, dict):
            risk = state.get("risk_assessment")
            intervention = state.get("intervention")
            similar_cases = state.get("similar_cases", [])
            final_report = state.get("final_report", "")
        else:
            # Fallback for object access
            risk = getattr(state, "risk_assessment", None)
            intervention = getattr(state, "intervention", None)
            similar_cases = getattr(state, "similar_cases", []) or []
            final_report = getattr(state, "final_report", "") or ""

        # Extract risk data
        risk_score = 0
        risk_level = "low"
        scam_type = ""
        risk_clues = []

        if risk:
            if isinstance(risk, dict):
                risk_score = risk.get("score", 0)
                risk_level = risk.get("level", "low")
                if hasattr(risk_level, 'value'):
                    risk_level = risk_level.value
                scam_type = risk.get("scam_type", "")
                risk_clues = risk.get("clues", [])
            else:
                risk_score = getattr(risk, "score", 0)
                level = getattr(risk, "level", None)
                risk_level = level.value if hasattr(level, 'value') else str(level or "low")
                scam_type = getattr(risk, "scam_type", "")
                risk_clues = getattr(risk, "clues", []) or []

        # Extract intervention data
        warning_message = ""
        guardian_alert = False
        alert_reason = ""
        action_items = []

        if intervention:
            if isinstance(intervention, dict):
                warning_message = intervention.get("warning_message", "")
                guardian_alert = intervention.get("guardian_alert", False)
                alert_reason = intervention.get("alert_reason", "")
                action_items = intervention.get("action_items", [])
            else:
                warning_message = getattr(intervention, "warning_message", "")
                guardian_alert = getattr(intervention, "guardian_alert", False)
                alert_reason = getattr(intervention, "alert_reason", "")
                action_items = getattr(intervention, "action_items", []) or []

        # Format similar cases
        formatted_cases = []
        for c in similar_cases[:3]:
            if isinstance(c, dict):
                formatted_cases.append({
                    "title": c.get("title", ""),
                    "content": c.get("content", "")[:200]
                })
            else:
                formatted_cases.append({
                    "title": getattr(c, "title", ""),
                    "content": (getattr(c, "content", "") or "")[:200]
                })

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "scam_type": scam_type,
            "risk_clues": risk_clues,
            "warning_message": warning_message,
            "guardian_alert": guardian_alert,
            "alert_reason": alert_reason,
            "action_items": action_items,
            "final_report": final_report,
            "similar_cases": formatted_cases,
        }


# Singleton instance
graph_client = GraphClient()
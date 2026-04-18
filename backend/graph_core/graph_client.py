"""
Graph client for backend API.
Provides a simplified interface to the anti-fraud workflow graph.
"""
import re
import sys
import inspect
from time import perf_counter
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional
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
from core.utils import normalize_user_role
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
        on_stream_chunk: Optional[Callable[[str], Awaitable[None] | None]] = None,
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

        normalized_role = normalize_user_role(user_role)

        state = GlobalState(
            input_text=text,
            input_files=input_files,
            user_context=UserContext(
                user_role=UserRole(normalized_role),
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
        graph_started_at = perf_counter()
        final_state: Any = None
        stream_progress = {
            "risk_signature": "",
            "intervention_signature": "",
            "intent_signature": "",
            "knowledge_signature": "",
            "final_report_len": 0,
        }
        aggregated_state: Dict[str, Any] = {}
        try:
            async for streamed_state in self.graph.astream(
                state,
                config={"configurable": {"thread_id": thread_id}},
                stream_mode="values",
            ):
                normalized_state = self._normalize_stream_state(streamed_state, aggregated_state)
                final_state = normalized_state
                if on_stream_chunk:
                    for chunk in self._build_stream_chunks(normalized_state, stream_progress):
                        await self._emit_stream_chunk(on_stream_chunk, chunk)
        except TypeError:
            # Older langgraph versions may not support stream_mode in astream.
            # Keep best-effort streaming instead of falling back to blocking ainvoke immediately.
            try:
                async for streamed_state in self.graph.astream(
                    state,
                    config={"configurable": {"thread_id": thread_id}},
                ):
                    normalized_state = self._normalize_stream_state(streamed_state, aggregated_state)
                    final_state = normalized_state
                    if on_stream_chunk:
                        for chunk in self._build_stream_chunks(normalized_state, stream_progress):
                            await self._emit_stream_chunk(on_stream_chunk, chunk)
            except Exception:
                final_state = await self.graph.ainvoke(
                    state,
                    config={"configurable": {"thread_id": thread_id}},
                )

        if final_state is None:
            final_state = await self.graph.ainvoke(
                state,
                config={"configurable": {"thread_id": thread_id}},
            )
        graph_elapsed_ms = round((perf_counter() - graph_started_at) * 1000, 2)

        formatted = self._format_response(final_state)
        timing = dict(formatted.get("performance_timing") or {})
        timing["graph_total_ms"] = graph_elapsed_ms
        formatted["performance_timing"] = timing
        snapshot = await self.runtime.record_detection(
            user_id=user_id or "anonymous",
            input_text=text or "",
            result=formatted,
        )
        formatted["detection_id"] = snapshot["detection_id"]
        return formatted

    async def _emit_stream_chunk(
        self,
        on_stream_chunk: Callable[[str], Awaitable[None] | None],
        chunk: str,
    ) -> None:
        maybe_result = on_stream_chunk(chunk)
        if inspect.isawaitable(maybe_result):
            await maybe_result

    def _build_stream_chunks(self, state: Any, stream_progress: Dict[str, Any]) -> List[str]:
        chunks: List[str] = []

        intent = state.get("intent") if isinstance(state, dict) else getattr(state, "intent", None)
        if intent:
            intent_name = ""
            confidence = ""
            if isinstance(intent, dict):
                intent_name = str(intent.get("name") or intent.get("intent") or "")
                confidence_raw = intent.get("confidence")
            else:
                intent_name = str(getattr(intent, "name", "") or getattr(intent, "intent", "") or "")
                confidence_raw = getattr(intent, "confidence", None)

            if confidence_raw is None:
                confidence = ""
            else:
                try:
                    confidence = f"{float(confidence_raw):.2f}"
                except (TypeError, ValueError):
                    confidence = str(confidence_raw)

            intent_signature = f"{intent_name}|{confidence}"
            if intent_signature.strip("|") and intent_signature != str(stream_progress.get("intent_signature") or ""):
                stream_progress["intent_signature"] = intent_signature
                intent_lines = ["## 当前识别意图"]
                if intent_name:
                    intent_lines.append(f"- 意图类型: {intent_name}")
                if confidence:
                    intent_lines.append(f"- 置信度: {confidence}")
                chunks.append("\n".join(intent_lines) + "\n\n")

        similar_cases = state.get("similar_cases") if isinstance(state, dict) else getattr(state, "similar_cases", None)
        top_case = ""
        if isinstance(similar_cases, list) and similar_cases:
            first_case = similar_cases[0]
            if isinstance(first_case, dict):
                top_case = str(first_case.get("title") or "")
            else:
                top_case = str(getattr(first_case, "title", "") or "")
        knowledge_signature = top_case
        if knowledge_signature and knowledge_signature != str(stream_progress.get("knowledge_signature") or ""):
            stream_progress["knowledge_signature"] = knowledge_signature
            chunks.append(f"## 关联案例检索\n- 命中案例: {top_case}\n\n")

        risk = state.get("risk_assessment") if isinstance(state, dict) else getattr(state, "risk_assessment", None)
        intervention = state.get("intervention") if isinstance(state, dict) else getattr(state, "intervention", None)
        final_report = state.get("final_report", "") if isinstance(state, dict) else getattr(state, "final_report", "")
        final_report = str(final_report or "")

        risk_score = 0
        risk_level = ""
        scam_type = ""
        risk_clues: List[str] = []
        if risk:
            if isinstance(risk, dict):
                risk_score = int(risk.get("score", 0) or 0)
                level = risk.get("level", "")
                risk_level = level.value if hasattr(level, "value") else str(level or "")
                scam_type = str(risk.get("scam_type", "") or "")
                risk_clues = [str(item) for item in (risk.get("clues") or []) if item]
            else:
                risk_score = int(getattr(risk, "score", 0) or 0)
                level = getattr(risk, "level", "")
                risk_level = level.value if hasattr(level, "value") else str(level or "")
                scam_type = str(getattr(risk, "scam_type", "") or "")
                risk_clues = [str(item) for item in (getattr(risk, "clues", []) or []) if item]

        risk_signature = f"{risk_score}|{risk_level}|{scam_type}|{'|'.join(risk_clues[:2])}"
        if risk_signature.strip("|") and risk_signature != str(stream_progress.get("risk_signature") or ""):
            stream_progress["risk_signature"] = risk_signature
            risk_lines = [
                "## 快速风险研判",
                f"- 风险等级: {risk_level or 'unknown'}",
                f"- 风险分数: {risk_score}/100",
            ]
            if scam_type:
                risk_lines.append(f"- 疑似类型: {scam_type}")
            if risk_clues:
                risk_lines.append(f"- 关键线索: {risk_clues[0]}")
            chunks.append("\n".join(risk_lines) + "\n\n")

        warning_message = ""
        action_items: List[str] = []
        if intervention:
            if isinstance(intervention, dict):
                warning_message = str(intervention.get("warning_message", "") or "")
                action_items = [str(item) for item in (intervention.get("action_items") or []) if item]
            else:
                warning_message = str(getattr(intervention, "warning_message", "") or "")
                action_items = [str(item) for item in (getattr(intervention, "action_items", []) or []) if item]

        intervention_signature = f"{warning_message}|{'|'.join(action_items[:2])}"
        if intervention_signature.strip("|") and intervention_signature != str(stream_progress.get("intervention_signature") or ""):
            stream_progress["intervention_signature"] = intervention_signature
            intervention_lines = ["## 立即建议"]
            if warning_message:
                intervention_lines.append(warning_message)
            if action_items:
                intervention_lines.extend([f"- {item}" for item in action_items[:3]])
            chunks.append("\n".join(intervention_lines) + "\n\n")

        previous_len = int(stream_progress.get("final_report_len") or 0)
        if len(final_report) > previous_len:
            delta = final_report[previous_len:]
            stream_progress["final_report_len"] = len(final_report)
            if delta:
                chunks.append(delta)

        return chunks

    def _normalize_stream_state(self, streamed_state: Any, aggregated_state: Dict[str, Any]) -> Any:
        if not isinstance(streamed_state, dict):
            return streamed_state

        state_like_keys = {
            "input_text",
            "input_files",
            "user_context",
            "perception_result",
            "intent",
            "similar_cases",
            "legal_basis",
            "risk_assessment",
            "short_term_memory_summary",
            "intervention",
            "guardian_notification",
            "final_report",
            "workflow_metadata",
        }
        node_names = {
            "perception",
            "intent_recognition",
            "knowledge_search",
            "risk_assessment",
            "risk_decision",
            "intervention_node",
            "report_generation",
        }

        # stream_mode="values": full/partial state snapshots.
        if any(key in state_like_keys for key in streamed_state.keys()):
            aggregated_state.update(streamed_state)
            return dict(aggregated_state)

        # Older default streaming may return per-node update payloads.
        # Example: {"report_generation": {"final_report": "..."}}
        for key, value in streamed_state.items():
            if key in node_names and isinstance(value, dict):
                aggregated_state.update(value)
            elif key in state_like_keys:
                aggregated_state[key] = value

        if aggregated_state:
            return dict(aggregated_state)
        return streamed_state

    def _format_response(self, state: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(state, dict):
            risk = state.get("risk_assessment")
            intervention = state.get("intervention")
            similar_cases = state.get("similar_cases", [])
            final_report = state.get("final_report", "")
            guardian_notification = state.get("guardian_notification")
            short_term_memory_summary = state.get("short_term_memory_summary", "")
            intent = state.get("intent")
            workflow_metadata = state.get("workflow_metadata") or {}
        else:
            risk = getattr(state, "risk_assessment", None)
            intervention = getattr(state, "intervention", None)
            similar_cases = getattr(state, "similar_cases", []) or []
            final_report = getattr(state, "final_report", "") or ""
            guardian_notification = getattr(state, "guardian_notification", None)
            short_term_memory_summary = getattr(state, "short_term_memory_summary", "") or ""
            intent = getattr(state, "intent", None)
            workflow_metadata = getattr(state, "workflow_metadata", {}) or {}

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
                formatted_cases.append(
                    {
                        "title": self._clean_report_placeholder(case.get("title", "")),
                        "content": self._clean_report_placeholder(case.get("content", ""))[:200],
                    }
                )
            else:
                formatted_cases.append(
                    {
                        "title": self._clean_report_placeholder(getattr(case, "title", "")),
                        "content": self._clean_report_placeholder(getattr(case, "content", "") or "")[:200],
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
            "final_report": self._clean_report_placeholder(final_report),
            "similar_cases": formatted_cases,
            "performance_timing": dict(workflow_metadata.get("performance_timing") or {}),
        }

    def _clean_report_placeholder(self, text: str) -> str:
        """Remove placeholder source text from reports and case snippets."""
        if not text:
            return ""

        cleaned = str(text)
        cleaned = re.sub(r"(:\s*)?内容来自种子URL（占位符）\.\.\.", "", cleaned)
        cleaned = re.sub(r"(:\s*)?内容来自种子URL\(占位符\)\.\.\.", "", cleaned)
        cleaned = re.sub(r"(:\s*)?内容来自种子URL（占位符）.*$", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"(:\s*)?内容来自种子URL\(占位符\).*$", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"(:\s*)?Content from seed URL \(placeholder\)\.\.\.", "", cleaned)
        cleaned = re.sub(r"(:\s*)?Content from seed URL \(placeholder\).*$", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"^\s*-\s*$", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()


graph_client = GraphClient()

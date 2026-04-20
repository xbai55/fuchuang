"""
Alert generator for fraud warnings.
"""
from typing import Any, Dict, List, Optional

from src.core.interfaces import LLMClient
from src.core.models import GlobalState, Intervention, RiskLevel
from src.core.utils import (
    build_role_prompt_guidance,
    format_role_profile_text,
    load_node_config,
    normalize_user_role,
)


class AlertGenerator:
    """Generates intervention actions and escalation plans."""

    DEFAULT_SYSTEM_PROMPT = (
        "You are an anti-fraud intervention planner. Return JSON with "
        "warning_message, guardian_alert, alert_reason, action_items, escalation_actions."
    )
    DEFAULT_USER_TEMPLATE = (
        "User role: {user_role}\n"
        "Role profile:\n{role_profile}\n"
        "Role-specific guidance:\n{role_prompt_guidance}\n"
        "Combined profile:\n{combined_profile}\n"
        "Guardian: {guardian_name}\n"
        "Short-term memory: {short_term_memory_summary}\n"
        "Risk score: {risk_score}/100\n"
        "Risk level: {risk_level}\n"
        "Scam type: {scam_type}\n"
        "Risk clues:\n{risk_clues}\n"
        "Input:\n{input_text}\n"
    )

    def __init__(self, llm_client: Optional[LLMClient] = None):
        config = load_node_config("intervention")
        self.system_prompt = config.get("system_prompt", self.DEFAULT_SYSTEM_PROMPT)
        self.user_template = config.get("user_prompt", self.DEFAULT_USER_TEMPLATE)
        self.llm = llm_client
        if self.llm is None:
            try:
                self.llm = LLMClient.from_config(config)
            except Exception:
                self.llm = None

    async def generate(self, state: GlobalState) -> Intervention:
        language = self._get_language(state)
        context = self._build_context(state)
        if self.llm is not None:
            try:
                response = await self.llm.achat(
                    system_prompt=self._build_system_prompt(language),
                    user_prompt=self._build_user_prompt(context, language),
                    parse_json=True,
                )
                if response.parsed_json:
                    return self._parse_intervention(response.parsed_json, state)
            except Exception as exc:
                print(f"[alert_generator] llm generation failed: {exc}")
        return self._fallback_intervention(state)

    def _get_language(self, state: GlobalState) -> str:
        metadata = state.workflow_metadata or {}
        language = str(metadata.get("language") or metadata.get("ui_language") or "zh-CN").strip()
        return "en-US" if language.lower().startswith("en") else "zh-CN"

    def _is_english(self, language: str) -> bool:
        return language == "en-US"

    def _build_system_prompt(self, language: str) -> str:
        if not self._is_english(language):
            return self.system_prompt
        return (
            f"{self.system_prompt}\n"
            "Output language rule: all user-facing JSON string values must be English only. "
            "Keep JSON keys unchanged. Do not output Chinese warning text, action items, or escalation labels."
        )

    def _build_user_prompt(self, context: Dict[str, Any], language: str) -> str:
        prompt = self.user_template.format(**context)
        if self._is_english(language):
            prompt += "\nReturn warning_message, alert_reason, action_items, and escalation action labels in English only.\n"
        return prompt

    def _build_context(self, state: GlobalState) -> Dict[str, Any]:
        risk = state.risk_assessment
        clues = risk.clues if risk and risk.clues else []
        normalized_role = normalize_user_role(state.user_context.user_role.value)
        language = self._get_language(state)
        combined_profile = str((state.workflow_metadata or {}).get("combined_profile_text") or "none")
        return {
            "input_text": state.get_combined_text() or "",
            "user_role": normalized_role,
            "role_profile": format_role_profile_text(normalized_role),
            "role_prompt_guidance": build_role_prompt_guidance(normalized_role, language),
            "combined_profile": combined_profile,
            "guardian_name": state.user_context.guardian_name or "not_set",
            "risk_score": risk.score if risk else 0,
            "risk_level": risk.level.value if risk else "low",
            "scam_type": risk.scam_type if risk and risk.scam_type else "unknown",
            "risk_clues": "\n".join(f"- {clue}" for clue in clues) if clues else "- none",
            "short_term_memory_summary": state.short_term_memory_summary or "none",
        }

    def _parse_intervention(self, data: Dict[str, Any], state: GlobalState) -> Intervention:
        action_items = data.get("action_items", [])
        if isinstance(action_items, str):
            action_items = [action_items]
        if isinstance(action_items, list):
            action_items = [str(item).strip() for item in action_items if str(item).strip()]
        else:
            action_items = []

        raw_escalation_actions = data.get("escalation_actions", [])
        escalation_actions: List[Dict[str, str]] = []
        if isinstance(raw_escalation_actions, list):
            for item in raw_escalation_actions:
                if isinstance(item, dict):
                    label = str(item.get("label") or item.get("text") or item.get("value") or "").strip()
                    if not label:
                        continue
                    action_type = str(item.get("type") or "action").strip() or "action"
                    value = str(item.get("value") or label).strip()
                    escalation_actions.append({"type": action_type, "label": label, "value": value})
                elif isinstance(item, str):
                    normalized = item.strip()
                    if normalized:
                        escalation_actions.append({"type": "action", "label": normalized, "value": normalized})

        intervention = Intervention(
            warning_message=data.get("warning_message", ""),
            guardian_alert=bool(data.get("guardian_alert", False)),
            alert_reason=data.get("alert_reason", ""),
            action_items=action_items,
            escalation_actions=escalation_actions,
        )
        if not intervention.escalation_actions:
            intervention.escalation_actions = self._build_escalation_actions(
                state,
                intervention.guardian_alert,
                language=self._get_language(state),
            )
        return intervention

    def _fallback_intervention(self, state: GlobalState) -> Intervention:
        if self._is_english(self._get_language(state)):
            return self._fallback_intervention_en(state)

        risk = state.risk_assessment
        if not risk:
            return Intervention(
                warning_message="暂时无法完成风险判断，请不要转账，也不要泄露验证码。",
                guardian_alert=False,
                action_items=["停止进一步操作", "保存聊天记录和转账页面截图"],
                escalation_actions=self._build_escalation_actions(state, False),
            )

        guardian_alert = risk.level == RiskLevel.HIGH and bool(
            state.user_context.guardian_name or state.user_context.guardian_phone or state.user_context.emergency_contacts
        )

        if risk.level == RiskLevel.LOW:
            warning = "当前线索偏弱，但仍建议核实对方身份后再继续交流。"
            actions = ["通过官方渠道二次核验", "不要点击陌生链接", "暂不提供验证码和银行卡信息"]
        elif risk.level == RiskLevel.MEDIUM:
            warning = f"检测到中风险诈骗迹象，疑似与“{risk.scam_type or '诈骗诱导'}”有关。"
            actions = ["立即停止转账", "核实对方身份", "将可疑信息发给家人或同事复核"]
        else:
            warning = f"检测到高风险诈骗，疑似与“{risk.scam_type or '诈骗诱导'}”有关，请立刻中止操作。"
            actions = ["立即停止转账和共享屏幕", "拨打 110 或 96110", "联系监护人/紧急联系人", "保留聊天和支付凭证"]

        return Intervention(
            warning_message=warning,
            guardian_alert=guardian_alert,
            alert_reason=f"Risk score {risk.score}/100 with level {risk.level.value}.",
            action_items=actions,
            escalation_actions=self._build_escalation_actions(state, guardian_alert),
        )

    def _fallback_intervention_en(self, state: GlobalState) -> Intervention:
        risk = state.risk_assessment
        if not risk:
            return Intervention(
                warning_message=(
                    "The risk engine did not return a complete assessment. "
                    "Pause sensitive actions until the content is verified."
                ),
                guardian_alert=False,
                alert_reason="No risk assessment was available.",
                action_items=[
                    "Do not transfer money or share verification codes",
                    "Verify the request through an official channel",
                ],
                escalation_actions=self._build_escalation_actions(state, False, language="en-US"),
            )

        guardian_alert = risk.level == RiskLevel.HIGH and bool(
            state.user_context.guardian_name or state.user_context.guardian_phone or state.user_context.emergency_contacts
        )

        if risk.level == RiskLevel.LOW:
            warning = "No clear high-risk fraud indicator was detected, but continue to verify unusual requests."
            actions = [
                "Keep the conversation in official channels",
                "Do not click suspicious links or install unknown apps",
                "Avoid sharing identity documents, passwords, or verification codes",
            ]
        elif risk.level == RiskLevel.MEDIUM:
            warning = (
                f"Suspicious fraud indicators were detected"
                f"{f' ({risk.scam_type})' if risk.scam_type else ''}. Verify before taking any action."
            )
            actions = [
                "Pause payment or account operations",
                "Verify the identity through an official phone number or app",
                "Preserve screenshots, audio, video, and chat records",
            ]
        else:
            warning = (
                f"High-risk fraud indicators were detected"
                f"{f' ({risk.scam_type})' if risk.scam_type else ''}. Stop the interaction immediately."
            )
            actions = [
                "Stop transfers, downloads, screen sharing, and code sharing immediately",
                "Call 110 or 96110 if money or account access is involved",
                "Notify a guardian or trusted emergency contact",
                "Preserve all evidence before deleting any message",
            ]

        return Intervention(
            warning_message=warning,
            guardian_alert=guardian_alert,
            alert_reason=f"Risk score {risk.score}/100 with level {risk.level.value}.",
            action_items=actions,
            escalation_actions=self._build_escalation_actions(state, guardian_alert, language="en-US"),
        )

    def _build_escalation_actions(
        self,
        state: GlobalState,
        guardian_alert: bool,
        language: str = "zh-CN",
    ) -> List[Dict[str, str]]:
        if self._is_english(language):
            actions = [
                {"type": "hotline", "label": "Call 110", "value": "110"},
                {"type": "hotline", "label": "Call anti-fraud hotline 96110", "value": "96110"},
            ]
            if guardian_alert and (state.user_context.guardian_name or state.user_context.guardian_phone):
                actions.append(
                    {
                        "type": "guardian",
                        "label": state.user_context.guardian_name or "Guardian",
                        "value": state.user_context.guardian_phone or "",
                    }
                )
            for contact in state.user_context.emergency_contacts[:3]:
                actions.append(
                    {
                        "type": "contact",
                        "label": contact.name or "Emergency contact",
                        "value": contact.phone or "",
                    }
                )
            return actions

        actions = [
            {"type": "hotline", "label": "拨打 110", "value": "110"},
            {"type": "hotline", "label": "反诈专线 96110", "value": "96110"},
        ]
        if guardian_alert and (state.user_context.guardian_name or state.user_context.guardian_phone):
            actions.append(
                {
                    "type": "guardian",
                    "label": state.user_context.guardian_name or "监护人",
                    "value": state.user_context.guardian_phone or "",
                }
            )
        for contact in state.user_context.emergency_contacts[:3]:
            actions.append(
                {
                    "type": "contact",
                    "label": contact.name or "紧急联系人",
                    "value": contact.phone or "",
                }
            )
        return actions

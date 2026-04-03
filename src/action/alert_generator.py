"""
Alert generator for fraud warnings.
"""
from typing import Any, Dict, List, Optional

from src.core.interfaces import LLMClient
from src.core.models import GlobalState, Intervention, RiskLevel
from src.core.utils import load_node_config


class AlertGenerator:
    """Generates intervention actions and escalation plans."""

    DEFAULT_SYSTEM_PROMPT = (
        "You are an anti-fraud intervention planner. Return JSON with "
        "warning_message, guardian_alert, alert_reason, action_items, escalation_actions."
    )
    DEFAULT_USER_TEMPLATE = (
        "User role: {user_role}\n"
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
        context = self._build_context(state)
        if self.llm is not None:
            try:
                response = await self.llm.achat(
                    system_prompt=self.system_prompt,
                    user_prompt=self.user_template.format(**context),
                    parse_json=True,
                )
                if response.parsed_json:
                    return self._parse_intervention(response.parsed_json, state)
            except Exception as exc:
                print(f"[alert_generator] llm generation failed: {exc}")
        return self._fallback_intervention(state)

    def _build_context(self, state: GlobalState) -> Dict[str, Any]:
        risk = state.risk_assessment
        clues = risk.clues if risk and risk.clues else []
        return {
            "input_text": state.get_combined_text() or "",
            "user_role": state.user_context.user_role.value,
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
            intervention.escalation_actions = self._build_escalation_actions(state, intervention.guardian_alert)
        return intervention

    def _fallback_intervention(self, state: GlobalState) -> Intervention:
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

    def _build_escalation_actions(self, state: GlobalState, guardian_alert: bool) -> List[Dict[str, str]]:
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

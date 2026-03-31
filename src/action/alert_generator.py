"""
Alert generator for fraud warnings.
Generates personalized warning messages based on risk level and user context.
"""
from typing import Dict, Any, List

from src.core.models import GlobalState, Intervention, RiskLevel, UserRole
from src.core.interfaces import LLMClient
from src.core.utils import load_node_config


class AlertGenerator:
    """
    Generates personalized fraud alert messages.

    Uses LLM to create context-aware warnings based on:
    - Risk level (low/medium/high)
    - User role (elderly/student/finance/general)
    - Risk assessment details
    """

    # Default system prompt
    DEFAULT_SYSTEM_PROMPT = """你是一位专业的反诈骗助手，同时具备自然对话能力。

请根据风险评估结果，为用户生成合适的回复：

1. **如果风险等级为 low（低风险）**：
   - 像普通聊天助手一样友好地回复用户的问题
   - 可以适当询问用户是否有具体内容需要分析
   - 保持友善、乐于助人的语气

2. **如果风险等级为 medium/high（中/高风险）**：
   - 立即给出风险警告，优先保护用户安全
   - 清晰说明风险点和防范建议

输出必须是一个有效的JSON对象，包含以下字段：
{
    "warning_message": "给用户的回复（低风险时友好对话，高风险时警告）",
    "guardian_alert": true/false，是否需要通知监护人,
    "alert_reason": "通知监护人的原因（如果需要）",
    "action_items": ["建议操作1", "建议操作2", ...]
}

针对不同用户类型的语气：
- elderly（老年人）：耐心、详细、关怀的语气
- student（学生）：活泼、易懂、有教育意义的语气
- finance（金融从业者）：专业、简洁、技术性的语气
- general（普通用户）：友好、自然的语气

请确保JSON格式正确。"""

    # Default user prompt template
    DEFAULT_USER_TEMPLATE = """请生成回复：

## 用户输入内容
{input_text}

## 用户画像
- 用户类型: {user_role}
- 监护人: {guardian_name}

## 风险评估结果
- 风险分数: {risk_score}/100
- 风险等级: {risk_level}
- 诈骗类型: {scam_type}
- 风险线索: {risk_clues}

## 系统检测信息
{perception_summary}

请根据风险等级选择合适的回复方式，输出JSON格式。"""

    def __init__(self, llm_client: 'LLMClient' = None):
        """
        Initialize alert generator.

        Args:
            llm_client: Optional LLM client
        """
        config = load_node_config("intervention")

        if llm_client:
            self.llm = llm_client
        else:
            self.llm = LLMClient.from_config(config)

        self.system_prompt = config.get("system_prompt", self.DEFAULT_SYSTEM_PROMPT)
        self.user_template = config.get("user_prompt", self.DEFAULT_USER_TEMPLATE)

    async def generate(self, state: GlobalState) -> Intervention:
        """
        Generate intervention based on risk assessment.

        Args:
            state: Current workflow state

        Returns:
            Intervention object
        """
        # Build context
        context = self._build_context(state)

        # Build user prompt
        user_prompt = self.user_template.format(**context)

        try:
            # Call LLM
            response = await self.llm.achat(
                system_prompt=self.system_prompt,
                user_prompt=user_prompt,
                parse_json=True,
            )

            # Parse result
            if response.parsed_json:
                return self._parse_intervention(response.parsed_json)
            else:
                return self._fallback_intervention(state)

        except Exception as e:
            print(f"[错误] 生成干预建议失败: {e}")
            return self._fallback_intervention(state)

    def _build_context(self, state: GlobalState) -> Dict[str, Any]:
        """
        Build context for prompt formatting.

        Args:
            state: Global state

        Returns:
            Context dictionary
        """
        risk = state.risk_assessment

        # Get user's input text
        input_text = state.get_combined_text() or "无输入内容"

        # Get risk clues
        clues = risk.clues if risk and risk.clues else []
        clues_text = "\n".join([f"- {c}" for c in clues]) if clues else "无"

        # Build perception summary
        perception_parts = []
        for result in state.perception_results:
            if result.fake_analysis and result.fake_analysis.is_fake:
                perception_parts.append(
                    f"检测到AI伪造内容 (置信度: {result.fake_analysis.fake_probability:.2f})"
                )
        perception_summary = "\n".join(perception_parts) if perception_parts else "无异常检测"

        return {
            "input_text": input_text,
            "user_role": state.user_context.user_role.value,
            "guardian_name": state.user_context.guardian_name or "未设置",
            "risk_score": risk.score if risk else 0,
            "risk_level": risk.level.value if risk else "low",
            "scam_type": risk.scam_type if risk else "未知",
            "risk_clues": clues_text,
            "perception_summary": perception_summary,
        }

    def _parse_intervention(self, data: Dict[str, Any]) -> Intervention:
        """
        Parse LLM response into Intervention.

        Args:
            data: Parsed JSON data

        Returns:
            Intervention object
        """
        return Intervention(
            warning_message=data.get("warning_message", ""),
            guardian_alert=data.get("guardian_alert", False),
            alert_reason=data.get("alert_reason", ""),
            action_items=data.get("action_items", []),
        )

    def _fallback_intervention(self, state: GlobalState) -> Intervention:
        """
        Generate fallback intervention when LLM fails.

        Args:
            state: Global state

        Returns:
            Fallback Intervention
        """
        risk = state.risk_assessment

        if not risk:
            return Intervention(
                warning_message="系统已接收您的请求，请保持警惕。",
                guardian_alert=False,
                action_items=["如有疑问请咨询专业人士"],
            )

        # Generate based on risk level
        if risk.level == RiskLevel.LOW:
            return Intervention(
                warning_message="未检测到明显风险，但请保持警惕。",
                guardian_alert=False,
                action_items=["谨慎对待陌生来电和信息"],
            )
        elif risk.level == RiskLevel.MEDIUM:
            return Intervention(
                warning_message=f"检测到潜在{risk.scam_type}风险，请谨慎处理。",
                guardian_alert=False,
                alert_reason="",
                action_items=[
                    "不要轻信对方身份",
                    "不要透露验证码和密码",
                    "如有疑问联系官方客服",
                ],
            )
        else:  # HIGH
            guardian_alert = state.user_context.guardian_name is not None
            return Intervention(
                warning_message=f"⚠️ 高风险警告！疑似{risk.scam_type}！",
                guardian_alert=guardian_alert,
                alert_reason=f"检测到高风险{risk.scam_type}，分数: {risk.score}/100",
                action_items=[
                    "立即停止任何转账操作",
                    "拨打110或反诈专线96110",
                    "不要透露验证码、密码等敏感信息",
                    "核实对方身份后再继续",
                ],
            )
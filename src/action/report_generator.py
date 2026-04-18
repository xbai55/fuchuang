"""
Report generator for final anti-fraud reports.
Compiles all analysis results into a comprehensive report.
"""
from datetime import datetime
import re
from typing import Any, Dict

from src.core.interfaces import LLMClient
from src.core.models import GlobalState
from src.core.utils import load_node_config


class ReportGenerator:
    """Generate language-aware anti-fraud reports."""

    def __init__(self, llm_client: "LLMClient" = None):
        config = load_node_config("report_generation")
        self.llm = llm_client or LLMClient.from_config(config)
        self.config = config

    async def generate(self, state: GlobalState) -> str:
        """Generate a full report in the user's preferred language."""
        language = self._get_language(state)
        context = self._build_context(state, language)
        system_prompt = self._build_system_prompt(language)
        user_prompt = self._build_user_prompt(context, language)

        try:
            response = await self.llm.achat(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                parse_json=False,
            )
            return self._format_report(response.content, state, language)
        except Exception as exc:
            print(f"[error] report generation failed: {exc}")
            return self._fallback_report(state, language)

    def _get_language(self, state: GlobalState) -> str:
        metadata = dict(state.workflow_metadata or {})
        language = str(metadata.get("language") or metadata.get("ui_language") or "zh-CN").strip()
        return "en-US" if language.lower().startswith("en") else "zh-CN"

    def _is_zh(self, language: str) -> bool:
        return language == "zh-CN"

    def _t(self, language: str, zh: str, en: str) -> str:
        return zh if self._is_zh(language) else en

    def _build_system_prompt(self, language: str) -> str:
        if self._is_zh(language):
            return """你是专业的反诈报告生成专家。

请基于输入信息生成一份完整、清晰、结构化的 Markdown 报告。
要求：
1. 整份报告必须使用简体中文。
2. 所有标题、字段名、风险等级、诈骗类型描述、建议内容都必须是中文。
3. 不要混用英文标签，例如 Risk Summary、Risk Level、Detailed Report。
4. 保持专业、客观、易懂。
"""

        return """You are a professional anti-fraud report generator.

Generate a complete, clear, structured Markdown report.
Requirements:
1. The entire report must be written in English.
2. All headings, field names, risk levels, scam type descriptions, and recommendations must be in English.
3. Do not mix Chinese labels such as 风险结论, 风险等级, 详细报告.
4. Keep the tone professional, objective, and easy to understand.
"""

    def _build_user_prompt(self, context: Dict[str, Any], language: str) -> str:
        if self._is_zh(language):
            return f"""请根据以下信息生成反诈安全报告：

## 输入内容
{context["input_text"]}

## 多模态分析
{context["perception_summary"]}

## 风险评估
- 风险分数: {context["risk_score"]}/100
- 风险等级: {context["risk_level"]}
- 诈骗类型: {context["scam_type"]}
- 风险线索:
{context["risk_clues"]}

## 干预措施
- 警告信息: {context["warning_message"]}
- 建议操作:
{context["action_items"]}

## 参考案例
{context["similar_cases"]}

## 法律依据
{context["legal_basis"]}

请输出完整的 Markdown 报告，且整份报告只使用简体中文。"""

        return f"""Generate an anti-fraud safety report using the following information:

## Input
{context["input_text"]}

## Multimodal Analysis
{context["perception_summary"]}

## Risk Assessment
- Risk Score: {context["risk_score"]}/100
- Risk Level: {context["risk_level"]}
- Scam Type: {context["scam_type"]}
- Risk Clues:
{context["risk_clues"]}

## Intervention
- Warning Message: {context["warning_message"]}
- Recommended Actions:
{context["action_items"]}

## Reference Cases
{context["similar_cases"]}

## Legal Basis
{context["legal_basis"]}

Return a complete Markdown report and ensure the whole report is written only in English."""

    def _build_context(self, state: GlobalState, language: str) -> Dict[str, Any]:
        input_text = state.get_combined_text()[:500]

        perception_parts = []
        for result in state.perception_results:
            summary = result.to_prompt_text()
            if summary:
                perception_parts.append(summary)
        perception_summary = "\n\n".join(perception_parts) if perception_parts else self._t(language, "无", "None")

        risk = state.risk_assessment
        risk_score = risk.score if risk else 0
        risk_level = self._localize_risk_level(risk.level.value if risk else "unknown", language)
        scam_type = self._localize_scam_type(risk.scam_type if risk else "", language)
        risk_clues = (
            "\n".join(f"- {self._clean_reference_content(clue)}" for clue in risk.clues)
            if risk and risk.clues
            else f"- {self._t(language, '无明显风险线索', 'No obvious risk clues')}"
        )

        intervention = state.intervention
        warning_message = self._clean_reference_content(
            intervention.warning_message if intervention and intervention.warning_message else self._t(language, "无", "None")
        )
        action_items = (
            "\n".join(f"- {self._clean_reference_content(item)}" for item in intervention.action_items)
            if intervention and intervention.action_items
            else f"- {self._t(language, '保持警惕，避免转账或泄露验证码', 'Stay cautious and avoid transfers or sharing verification codes')}"
        )

        case_sections = []
        for case in state.similar_cases[:3]:
            cleaned_content = self._clean_reference_content(case.content)
            if not cleaned_content:
                continue
            title = self._clean_reference_content(case.title) or self._t(language, "参考案例", "Reference Case")
            case_sections.append(f"### {title}\n{cleaned_content[:200]}...")
        similar_cases = "\n\n".join(case_sections) if case_sections else self._t(language, "暂无相似案例", "No similar cases")

        cleaned_legal_basis = [
            cleaned for item in state.legal_basis
            if (cleaned := self._clean_reference_content(item))
        ]
        legal_basis = (
            "\n".join(f"- {item}" for item in cleaned_legal_basis)
            if cleaned_legal_basis
            else f"- {self._t(language, '暂无法律依据', 'No legal basis available')}"
        )

        return {
            "input_text": input_text,
            "perception_summary": perception_summary,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "scam_type": scam_type,
            "risk_clues": risk_clues,
            "warning_message": warning_message,
            "action_items": action_items,
            "similar_cases": similar_cases,
            "legal_basis": legal_basis,
        }

    def _localize_risk_level(self, risk_level: str, language: str) -> str:
        mapping = {
            "low": self._t(language, "低风险", "Low Risk"),
            "medium": self._t(language, "中风险", "Medium Risk"),
            "high": self._t(language, "高风险", "High Risk"),
            "unknown": self._t(language, "未知", "Unknown"),
        }
        return mapping.get((risk_level or "unknown").lower(), risk_level or mapping["unknown"])

    def _localize_scam_type(self, scam_type: str, language: str) -> str:
        value = (scam_type or "").strip()
        if not value:
            return self._t(language, "未识别", "Not identified")

        normalized = value.lower()
        known_types = [
            (["phishing for personal information", "personal information phishing", "个人信息钓鱼", "网络钓鱼个人信息"], "个人信息钓鱼", "Phishing for Personal Information"),
            (["identity impersonation scam", "identity impersonation", "身份冒充诈骗"], "身份冒充诈骗", "Identity Impersonation Scam"),
            (["fake customer service scam", "customer service scam", "冒充客服诈骗"], "冒充客服诈骗", "Fake Customer Service Scam"),
            (["investment fraud", "investment scam", "虚假投资理财诈骗"], "虚假投资理财诈骗", "Investment Fraud"),
            (["part-time job scam", "brush order scam", "兼职刷单诈骗"], "兼职刷单诈骗", "Part-time Job Scam"),
            (["fake loan scam", "loan scam", "虚假贷款诈骗"], "虚假贷款诈骗", "Fake Loan Scam"),
            (["pig butchering scam", "杀猪盘诈骗"], "杀猪盘诈骗", "Pig Butchering Scam"),
            (["campus loan scam", "校园贷诈骗"], "校园贷诈骗", "Campus Loan Scam"),
            (["public authority impersonation scam", "冒充公检法诈骗"], "冒充公检法诈骗", "Public Authority Impersonation Scam"),
            (["credit repair scam", "征信修复诈骗"], "征信修复诈骗", "Credit Repair Scam"),
            (["ai face swap scam", "ai换脸诈骗"], "AI换脸诈骗", "AI Face Swap Scam"),
            (["potential scam", "潜在诈骗"], "潜在诈骗", "Potential Scam"),
            (["not identified", "unknown", "未识别", "未知"], "未识别", "Not identified"),
        ]

        for aliases, zh_value, en_value in known_types:
            if any(alias in normalized for alias in aliases):
                return zh_value if self._is_zh(language) else en_value
        return value

    def _clean_reference_content(self, text: str) -> str:
        """Remove placeholder text from retrieved references before reporting."""
        if not text:
            return ""

        cleaned = str(text).strip()
        cleaned = re.sub(r"内容来自种子URL（占位符）.*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"内容来自种子URL\(占位符\).*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"内容来自种子URL.*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"Content from seed URL \(placeholder\).*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^\s*-\s*$", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        cleaned = re.sub(r"\s+\.\.\.$", "", cleaned)
        return cleaned.strip(" \n-:：")

    def _format_report(self, content: str, state: GlobalState, language: str) -> str:
        """Add a localized header and timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        risk = state.risk_assessment
        risk_level = self._localize_risk_level(risk.level.value if risk else "unknown", language)
        scam_type = self._localize_scam_type(risk.scam_type if risk else "", language)

        if self._is_zh(language):
            header = f"""# 反诈安全分析报告

**生成时间**: {timestamp}
**风险等级**: {risk_level}
**风险分数**: {risk.score if risk else 0}/100
**诈骗类型**: {scam_type}

---

"""
        else:
            header = f"""# Anti-fraud Safety Analysis Report

**Generated At**: {timestamp}
**Risk Level**: {risk_level}
**Risk Score**: {risk.score if risk else 0}/100
**Scam Type**: {scam_type}

---

"""

        return header + self._clean_reference_content(content)

    def _fallback_report(self, state: GlobalState, language: str) -> str:
        """Fallback report when LLM generation fails."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        risk = state.risk_assessment
        intervention = state.intervention
        risk_level = self._localize_risk_level(risk.level.value if risk else "unknown", language)
        scam_type = self._localize_scam_type(risk.scam_type if risk else "", language)

        if self._is_zh(language):
            parts = [
                "# 反诈安全分析报告",
                "",
                f"**生成时间**: {timestamp}",
                f"**风险等级**: {risk_level}",
                f"**风险分数**: {risk.score if risk else 0}/100",
                f"**诈骗类型**: {scam_type}",
                "",
                "## 执行摘要",
                "",
                intervention.warning_message if intervention and intervention.warning_message else "系统已完成风险分析。",
                "",
                "## 建议措施",
                "",
            ]
        else:
            parts = [
                "# Anti-fraud Safety Analysis Report",
                "",
                f"**Generated At**: {timestamp}",
                f"**Risk Level**: {risk_level}",
                f"**Risk Score**: {risk.score if risk else 0}/100",
                f"**Scam Type**: {scam_type}",
                "",
                "## Executive Summary",
                "",
                intervention.warning_message if intervention and intervention.warning_message else "The system completed the risk analysis.",
                "",
                "## Recommended Actions",
                "",
            ]

        if intervention and intervention.action_items:
            for item in intervention.action_items:
                parts.append(f"- {item}")
        else:
            parts.append(
                f"- {self._t(language, '保持警惕，谨慎对待可疑信息', 'Stay alert and treat suspicious messages with caution')}"
            )

        parts.extend([
            "",
            f"## {self._t(language, '风险提示', 'Risk Notes')}",
            "",
        ])

        if risk and risk.clues:
            for clue in risk.clues:
                parts.append(f"- {clue}")
        else:
            parts.append(f"- {self._t(language, '未检测到明显风险特征', 'No obvious risk indicators were detected')}")

        return "\n".join(parts)

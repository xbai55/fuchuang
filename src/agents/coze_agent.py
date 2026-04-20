import json
import os
import sqlite3
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.core.utils import get_role_profile, normalize_user_role
from src.evolution.runtime import get_evolution_runtime


_SHARED_AGENT_LLM: Optional[ChatOpenAI] = None


def _normalize_language(language: Optional[str]) -> str:
    value = (language or "").strip().lower()
    return "en-US" if value.startswith("en") else "zh-CN"


def _get_shared_agent_llm() -> Optional[ChatOpenAI]:
    global _SHARED_AGENT_LLM
    if _SHARED_AGENT_LLM is not None:
        return _SHARED_AGENT_LLM

    model_name = os.getenv("LLM_MODEL", "moonshot-v1-8k")
    base_url = os.getenv("LLM_BASE_URL", "https://api.moonshot.cn/v1")
    api_key = os.getenv("LLM_API_KEY") or os.getenv("MOONSHOT_API_KEY") or os.getenv("OPENAI_API_KEY")

    if not api_key:
        return None

    _SHARED_AGENT_LLM = ChatOpenAI(
        model=model_name,
        temperature=0.7,
        max_tokens=2000,
        api_key=api_key,
        base_url=base_url,
    )
    return _SHARED_AGENT_LLM


async def warmup_coze_agent_llm() -> Dict[str, str]:
    llm = _get_shared_agent_llm()
    if llm is None:
        return {"status": "skipped", "reason": "missing_api_key"}

    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content="你是服务预热助手。"),
                HumanMessage(content="仅回复OK"),
            ]
        )
        content = str(getattr(response, "content", ""))
        return {"status": "ok", "reply": content[:16] if content else "OK"}
    except Exception as exc:
        return {"status": "failed", "reason": str(exc)}


class CozeAgent:
    """Role-aware agent with local tool execution."""

    TOOL_CATALOG = {
        "lookup_guardian_contacts": "Read guardian and emergency contacts for the current user.",
        "lookup_recent_detection_history": "Read recent fraud detection history for the current user.",
        "lookup_emergency_hotlines": "Provide anti-fraud hotlines and police numbers.",
        "build_safety_action_plan": "Generate a concrete anti-fraud action plan for the current request.",
    }

    def __init__(self, user_id: int, user_role: str = "general", language: str = "zh-CN"):
        self.user_id = user_id
        self.user_role = normalize_user_role(user_role)
        self.language = _normalize_language(language)
        self.runtime = get_evolution_runtime()
        self.db_path = Path(__file__).resolve().parents[2] / "fraud_detection.db"
        self.llm = _get_shared_agent_llm()

        self.system_prompt = self._with_language_instruction(self._get_system_prompt())
        self.conversation_history: List[Any] = []

    def _is_english(self) -> bool:
        return self.language == "en-US"

    def _with_language_instruction(self, prompt: str) -> str:
        if not self._is_english():
            return prompt
        return (
            f"{prompt}\n\n"
            "Output language rule: answer in English only. Keep all user-facing text, suggestions, "
            "safety plans, and explanations in English."
        )

    def _get_system_prompt(self) -> str:
        prompts = {
            "elderly": "你是一位耐心、友善的反诈助手，用通俗易懂的语言帮助老年用户识别风险并给出明确步骤。",
            "student": "你是一位轻松直接的反诈助手，帮助学生快速判断风险并给出可执行建议。",
            "finance": "你是一位专业严谨的反诈顾问，面向财会场景输出审慎、规范的建议。",
            "general": "你是一位专业的反诈助手，优先给出清晰、实用、可立即执行的防骗建议。",
        }
        profile = get_role_profile(self.user_role)
        return (
            "你是一位专业反诈助手，需要根据用户角色提供差异化提醒。\n"
            f"当前角色: {profile['label']}({profile['role_key']})\n"
            f"沟通风格: {profile['tone']}\n"
            f"重点风险: {profile['focus']}\n"
            f"安全教育重点: {profile['education']}\n"
            "请优先给出简洁、可执行、符合该角色行为习惯和风险偏好的建议。"
        )

    async def chat(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        tool_calls, tool_context = await self._execute_tools(message, context or {})
        messages = [SystemMessage(content=self.system_prompt)]

        if tool_context:
            messages.append(
                SystemMessage(
                    content="以下是你可以使用的本地工具结果，请结合它们回答，不要编造未提供的数据：\n"
                    + tool_context
                )
            )

        messages.extend(self.conversation_history)
        user_content = message
        if self._is_english():
            user_content = "Please answer in English only.\n\n" + user_content
        if context:
            user_content += "\n\n上下文:\n" + json.dumps(context, ensure_ascii=False)
        messages.append(HumanMessage(content=user_content))

        if self.llm is not None:
            response = await self.llm.ainvoke(messages)
            response_text = response.content
        else:
            response_text = self._build_fallback_response(message, tool_calls)

        self.conversation_history.append(HumanMessage(content=message))
        self.conversation_history.append(AIMessage(content=response_text))
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        return {
            "message": response_text,
            "suggestions": self._generate_suggestions(message, response_text),
            "tool_calls": tool_calls,
            "conversation_id": conversation_id or f"conv_{self.user_id}_{len(self.conversation_history)}",
        }

    async def stream_chat(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream agent response chunks and emit final metadata payload."""
        tool_calls, tool_context = await self._execute_tools(message, context or {})
        messages = [SystemMessage(content=self.system_prompt)]

        if tool_context:
            messages.append(
                SystemMessage(
                    content="以下是你可以使用的本地工具结果，请结合它们回答，不要编造未提供的数据：\n"
                    + tool_context
                )
            )

        messages.extend(self.conversation_history)
        user_content = message
        if self._is_english():
            user_content = "Please answer in English only.\n\n" + user_content
        if context:
            user_content += "\n\n上下文:\n" + json.dumps(context, ensure_ascii=False)
        messages.append(HumanMessage(content=user_content))

        response_parts: List[str] = []

        if self.llm is not None:
            try:
                async for chunk in self.llm.astream(messages):
                    chunk_text = self._extract_chunk_text(getattr(chunk, "content", ""))
                    if not chunk_text:
                        continue
                    response_parts.append(chunk_text)
                    yield {
                        "event": "agent_chunk",
                        "chunk": chunk_text,
                    }
            except Exception:
                # Fallback to single invoke to avoid failing the whole conversation.
                response = await self.llm.ainvoke(messages)
                fallback_text = self._extract_chunk_text(getattr(response, "content", ""))
                for chunk_text in self._split_text_chunks(fallback_text):
                    response_parts.append(chunk_text)
                    yield {
                        "event": "agent_chunk",
                        "chunk": chunk_text,
                    }
        else:
            fallback_text = self._build_fallback_response(message, tool_calls)
            for chunk_text in self._split_text_chunks(fallback_text):
                response_parts.append(chunk_text)
                yield {
                    "event": "agent_chunk",
                    "chunk": chunk_text,
                }

        response_text = "".join(response_parts).strip()
        if not response_text:
            response_text = self._build_fallback_response(message, tool_calls)

        self.conversation_history.append(HumanMessage(content=message))
        self.conversation_history.append(AIMessage(content=response_text))
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        final_payload = {
            "message": response_text,
            "suggestions": self._generate_suggestions(message, response_text),
            "tool_calls": tool_calls,
            "conversation_id": conversation_id or f"conv_{self.user_id}_{len(self.conversation_history)}",
        }
        yield {
            "event": "agent_completed",
            "data": final_payload,
        }

    async def _execute_tools(
        self,
        message: str,
        context: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], str]:
        selected_tools = self._select_tools(message, context)
        tool_calls: List[Dict[str, Any]] = []
        context_blocks: List[str] = []

        for tool_name in selected_tools:
            result = self._run_tool(tool_name, message, context)
            tool_calls.append(
                {
                    "tool": tool_name,
                    "arguments": {"message": message},
                    "result": result,
                }
            )
            context_blocks.append(f"[{tool_name}]\n{json.dumps(result, ensure_ascii=False)}")

        return tool_calls, "\n\n".join(context_blocks)

    def _select_tools(self, message: str, context: Dict[str, Any]) -> List[str]:
        text = (message or "").lower()
        selected: List[str] = []

        if any(keyword in text for keyword in ["家人", "监护", "联系人", "联系谁", "紧急联系人"]):
            selected.append("lookup_guardian_contacts")
        if any(keyword in text for keyword in ["历史", "之前", "最近", "记录", "风险趋势"]):
            selected.append("lookup_recent_detection_history")
        if any(keyword in text for keyword in ["报警", "举报", "热线", "110", "96110"]):
            selected.append("lookup_emergency_hotlines")
        if any(keyword in text for keyword in ["怎么办", "现在怎么做", "下一步", "处理", "求助"]):
            selected.append("build_safety_action_plan")

        if context.get("force_tools"):
            for tool_name in context["force_tools"]:
                if tool_name in self.TOOL_CATALOG and tool_name not in selected:
                    selected.append(tool_name)

        if not selected:
            selected.append("build_safety_action_plan")
        return selected

    def _run_tool(self, tool_name: str, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        handlers = {
            "lookup_guardian_contacts": self._lookup_guardian_contacts,
            "lookup_recent_detection_history": self._lookup_recent_detection_history,
            "lookup_emergency_hotlines": self._lookup_emergency_hotlines,
            "build_safety_action_plan": self._build_safety_action_plan,
        }
        try:
            return handlers[tool_name](message=message, context=context)
        except Exception as exc:
            return {"error": str(exc), "tool": tool_name}

    def _lookup_guardian_contacts(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        contacts: List[Dict[str, Any]] = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT name, phone, email, contact_relationship, is_guardian
                FROM contacts
                WHERE user_id = ?
                ORDER BY is_guardian DESC, created_at DESC
                """,
                (self.user_id,),
            ).fetchall()
            contacts = [
                {
                    "name": row["name"],
                    "phone": row["phone"],
                    "email": row["email"],
                    "relationship": row["contact_relationship"],
                    "is_guardian": bool(row["is_guardian"]),
                }
                for row in rows
            ]

        return {
            "count": len(contacts),
            "contacts": contacts,
            "primary_guardian": next((item for item in contacts if item["is_guardian"]), None),
        }

    def _lookup_recent_detection_history(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        runtime_history = self.runtime.get_recent_detections(str(self.user_id), limit=5)
        db_history: List[Dict[str, Any]] = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT user_message, bot_response, risk_score, risk_level, scam_type, guardian_alert, created_at
                FROM chat_history
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 5
                """,
                (self.user_id,),
            ).fetchall()
            db_history = [
                {
                    "user_message": row["user_message"],
                    "bot_response": row["bot_response"],
                    "risk_score": row["risk_score"],
                    "risk_level": row["risk_level"],
                    "scam_type": row["scam_type"],
                    "guardian_alert": bool(row["guardian_alert"]),
                    "created_at": row["created_at"],
                }
                for row in rows
            ]

        return {
            "runtime_history": runtime_history,
            "db_history": db_history,
        }

    def _lookup_emergency_hotlines(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        if self._is_english():
            return {
                "hotlines": [
                    {"name": "Police emergency hotline", "phone": "110"},
                    {"name": "Anti-fraud hotline", "phone": "96110"},
                ],
                "tips": [
                    "If money has been transferred, contact the bank and police immediately.",
                    "Preserve chat records, transfer receipts, phone numbers, links, and screenshots.",
                ],
            }

        return {
            "hotlines": [
                {"name": "公安报警", "phone": "110"},
                {"name": "国家反诈专线", "phone": "96110"},
            ],
            "tips": [
                "如果已经转账，先联系银行尝试止付。",
                "保存聊天记录、转账截图、通话记录等证据。",
            ],
        }

    def _build_safety_action_plan(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        if self._is_english():
            urgent = any(
                keyword in message.lower()
                for keyword in ["transfer", "verification code", "remote", "screen share", "bank card", "payment"]
            )
            actions = [
                "Pause transfers, payments, downloads, and screen sharing",
                "Verify the request through an official phone number, website, or app",
                "Preserve screenshots, links, phone numbers, and transaction records",
            ]
            if urgent:
                actions.extend(
                    [
                        "Contact your guardian or emergency contact immediately",
                        "Call 110 or 96110 if money or account access is involved",
                    ]
                )
            return {"urgent": urgent, "actions": actions}

        urgent = any(keyword in message for keyword in ["转账", "验证码", "下载", "屏幕共享", "银行卡", "付款"])
        actions = [
            "停止继续聊天、转账或提供验证码。",
            "改用官方电话或官方 App 自行核实对方身份。",
            "保留聊天记录、链接、截图和转账凭证。",
        ]
        if urgent:
            actions.extend(
                [
                    "如果已付款，立即联系银行和支付平台申请止付。",
                    "视情况拨打 110 或 96110。",
                ]
            )
        return {
            "urgent": urgent,
            "actions": actions,
        }

    def _generate_suggestions(self, user_message: str, bot_response: str) -> List[str]:
        if self._is_english():
            return [
                "Check whether this is a scam",
                "Build a safety action plan",
                "Show emergency contacts and hotlines",
            ]

        if any(keyword in user_message for keyword in ["转账", "付款", "银行卡"]):
            return ["帮我判断这条转账要求是否可信", "给我一个立即执行的止损步骤", "需要联系谁比较合适"]
        if any(keyword in user_message for keyword in ["报警", "举报", "维权"]):
            return ["告诉我报警前要准备哪些证据", "帮我整理一份报案要点", "查询我的紧急联系人"]
        return ["帮我判断这是不是诈骗", "给我一个简短的防骗步骤", "查看我最近的风险记录"]

    def _extract_chunk_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                    continue
                if isinstance(item, dict):
                    text_value = item.get("text")
                    if isinstance(text_value, str):
                        parts.append(text_value)
                        continue
                    content_value = item.get("content")
                    if isinstance(content_value, str):
                        parts.append(content_value)
            return "".join(parts)

        return str(content or "")

    def _split_text_chunks(self, text: str, chunk_size: int = 80) -> List[str]:
        normalized = (text or "").replace("\r\n", "\n")
        if not normalized:
            return []

        chunks: List[str] = []
        for start in range(0, len(normalized), chunk_size):
            chunks.append(normalized[start:start + chunk_size])
        return chunks

    def _build_fallback_response(self, message: str, tool_calls: List[Dict[str, Any]]) -> str:
        if self._is_english():
            lines = ["I have reviewed the available context and generated a safety-focused response."]
            for call in tool_calls:
                if call["tool"] == "lookup_guardian_contacts":
                    primary = call["result"].get("primary_guardian")
                    if primary:
                        lines.append(f"Primary guardian: {primary['name']}, phone: {primary['phone']}.")
                if call["tool"] == "lookup_emergency_hotlines":
                    hotlines = ", ".join(item["phone"] for item in call["result"].get("hotlines", []))
                    if hotlines:
                        lines.append(f"Emergency hotlines: {hotlines}.")
                if call["tool"] == "build_safety_action_plan":
                    actions = call["result"].get("actions", [])
                    if actions:
                        lines.append("Suggested actions: " + "; ".join(str(item) for item in actions[:4]))
            if len(lines) == 1:
                lines.append("Pause sensitive actions, verify through official channels, and keep evidence.")
            return "\n".join(lines)

        lines = ["当前无法连接大模型，我先基于本地工具结果给你建议。"]
        for call in tool_calls:
            if call["tool"] == "lookup_guardian_contacts":
                primary = call["result"].get("primary_guardian")
                if primary:
                    lines.append(f"你的主要联系人是 {primary['name']}，电话 {primary['phone']}。")
            if call["tool"] == "lookup_emergency_hotlines":
                hotlines = ", ".join(item["phone"] for item in call["result"].get("hotlines", []))
                if hotlines:
                    lines.append(f"可立即拨打: {hotlines}。")
            if call["tool"] == "build_safety_action_plan":
                actions = call["result"].get("actions", [])
                if actions:
                    lines.append("建议步骤: " + "；".join(actions[:4]))
        if len(lines) == 1:
            lines.append("先不要转账，不要提供验证码，改用官方渠道核实对方身份。")
        return "\n".join(lines)

    def reset_conversation(self):
        self.conversation_history = []

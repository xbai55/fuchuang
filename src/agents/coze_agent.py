import os
import json
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

class CozeAgent:
    """
    Coze Agent 集成类
    支持多轮对话、工具调用、上下文管理
    """
    
    def __init__(self, user_id: int, user_role: str = "general"):
        self.user_id = user_id
        self.user_role = user_role
        
        # 初始化 LLM - 从环境变量读取配置
        model_name = os.getenv("LLM_MODEL", "moonshot-v1-8k")
        base_url = os.getenv("LLM_BASE_URL", "https://api.moonshot.cn/v1")
        api_key = os.getenv("LLM_API_KEY") or os.getenv("MOONSHOT_API_KEY") or os.getenv("OPENAI_API_KEY")

        self.llm = ChatOpenAI(
            model=model_name,
            temperature=0.7,
            max_tokens=2000,
            api_key=api_key,
            base_url=base_url,
        )
        
        # 系统提示词
        self.system_prompt = self._get_system_prompt()
        
        # 对话历史（实际应用中应该从数据库加载）
        self.conversation_history = []
    
    def _get_system_prompt(self) -> str:
        """根据用户角色获取系统提示词"""
        prompts = {
            "elderly": "你是一位耐心、友善的反诈助手，用通俗易懂的语言为老年人提供防诈骗建议。",
            "student": "你是一位年轻活力的反诈助手，用轻松的方式为学生群体提供防骗指导。",
            "finance": "你是一位专业、严谨的反诈顾问，为财会人员提供专业的风险防控建议。",
            "general": "你是一位专业的反诈助手，为用户提供准确、实用的防诈骗建议。"
        }
        return prompts.get(self.user_role, prompts["general"])
    
    async def chat(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        聊天方法
        
        Args:
            message: 用户消息
            conversation_id: 对话 ID（用于多轮对话）
            context: 上下文信息（可包含之前分析的风险分析结果等）
        
        Returns:
            回复字典
        """
        # 构建消息
        messages = [
            SystemMessage(content=self.system_prompt),
            *self.conversation_history,
            HumanMessage(content=message)
        ]
        
        # 如果有上下文信息，追加到消息中
        if context:
            context_info = f"\n\n【上下文信息】\n{json.dumps(context, ensure_ascii=False)}"
            messages[-1] = HumanMessage(content=messages[-1].content + context_info)
        
        # 调用 LLM
        response = await self.llm.ainvoke(messages)
        
        # 保存对话历史
        self.conversation_history.append(HumanMessage(content=message))
        self.conversation_history.append(AIMessage(content=response.content))
        
        # 限制历史长度
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]
        
        return {
            "message": response.content,
            "suggestions": self._generate_suggestions(message, response.content),
            "tool_calls": [],
            "conversation_id": conversation_id or f"conv_{self.user_id}_{len(self.conversation_history)}"
        }
    
    def _generate_suggestions(self, user_message: str, bot_response: str) -> List[str]:
        """生成后续建议问题"""
        # 简单的关键词匹配，实际可以使用 LLM 生成
        if "诈骗" in user_message or "骗子" in user_message:
            return [
                "如何识别诈骗电话？",
                "遇到诈骗应该怎么办？",
                "如何保护个人信息安全？"
            ]
        elif "转账" in user_message or "汇款" in user_message:
            return [
                "转账前需要注意什么？",
                "如何确认对方身份？",
                "大额转账有什么风险？"
            ]
        elif "链接" in user_message or "网址" in user_message:
            return [
                "如何判断链接是否安全？",
                "点击了可疑链接怎么办？",
                "如何防范钓鱼网站？"
            ]
        else:
            return [
                "还有其他问题吗？",
                "需要我帮你分析具体内容吗？"
            ]
    
    def reset_conversation(self):
        """重置对话历史"""
        self.conversation_history = []

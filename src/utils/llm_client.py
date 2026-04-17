import os
from openai import OpenAI

def get_llm_client() -> OpenAI:
    return OpenAI(
        api_key=os.environ.get("ARK_API_KEY", ""),
        base_url=os.environ.get("ARK_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    )


def call_llm(
    messages: list,
    model: str = "qwen-plus",
    temperature: float = 0.3,
    max_tokens: int = 4000,
    top_p: float = 0.95,
) -> str:
    client = get_llm_client()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
    )
    return response.choices[0].message.content or ""

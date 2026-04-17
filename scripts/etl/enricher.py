"""
LLM-based enrichment for fraud cases.
Uses the same Doubao model as the main workflow.
Requires env vars: ARK_API_KEY (or OPENAI_API_KEY), ARK_BASE_URL
"""

import json
import os
from openai import OpenAI

_SCAM_TYPES = "刷单、理财、公检法、AI换脸、身份冒充、虚假征信、兼职诈骗、网络购物、情感诈骗、游戏诈骗"

_SYSTEM_PROMPT = f"""你是反诈案例标注专家。对给定的诈骗案例文本，提取结构化信息。
诈骗类型参考：{_SCAM_TYPES}，也可自定义。
严格返回 JSON，格式：
{{
  "scam_type": "诈骗类型",
  "risk_keywords": ["关键词1", "关键词2", ...],
  "legal_references": "相关法律条文，如无则留空",
  "severity": "high|medium|low"
}}"""

_USER_PROMPT = "案例文本：\n{text}"


def enrich(cleaned_text: str) -> dict:
    """
    Returns dict with keys: scam_type, risk_keywords (list), legal_references, severity.
    Falls back to safe defaults on any error.
    """
    client = _get_client()
    if client is None:
        return _default_enrichment()

    try:
        resp = client.chat.completions.create(
            model=os.getenv("ENRICHMENT_MODEL", "doubao-seed-1-8-251228"),
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _USER_PROMPT.format(text=cleaned_text[:2000])},
            ],
            temperature=0.2,
            max_tokens=512,
            response_format={"type": "json_object"},
        )
        result = json.loads(resp.choices[0].message.content)
        return _validate(result)
    except Exception as e:
        print(f"[enricher] LLM call failed: {e}, using defaults")
        return _default_enrichment()


def _get_client():
    api_key = os.getenv("ARK_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("ARK_BASE_URL")
    if not api_key:
        print("[enricher] No API key found; skipping LLM enrichment")
        return None
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def _validate(result: dict) -> dict:
    return {
        "scam_type": str(result.get("scam_type", "未知")),
        "risk_keywords": result.get("risk_keywords", []) if isinstance(result.get("risk_keywords"), list) else [],
        "legal_references": str(result.get("legal_references", "")),
        "severity": result.get("severity", "medium") if result.get("severity") in ("high", "medium", "low") else "medium",
    }


def _default_enrichment() -> dict:
    return {"scam_type": "未知", "risk_keywords": [], "legal_references": "", "severity": "medium"}

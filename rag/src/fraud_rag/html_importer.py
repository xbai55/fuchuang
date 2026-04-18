"""
HTML 案例导入器
支持从本地 HTML 文件或抓取网页内容中提取诈骗案例，
并转换为 KnowledgeDocument 对象供 RAG 管道消费。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .models import ImageAsset, KnowledgeDocument
from .text import build_summary, clean_text
from .utils import canonicalize_url, sha1_text, unique_preserve

# ── 关键词映射（与 crawler.py 保持一致）─────────────────────────────────────

_TAG_KEYWORDS: dict[str, list[str]] = {
    "电信网络诈骗": ["电信网络诈骗"],
    "跨境": ["跨境电诈"],
    "投资": ["投资诈骗"],
    "黄金": ["投资诈骗"],
    "荐股": ["荐股引流"],
    "理财": ["投资诈骗"],
    "培训": ["培训诈骗"],
    "招聘": ["求职诈骗"],
    "兼职": ["兼职骗局"],
    "AI拟声": ["AI拟声诈骗"],
    "换音": ["AI拟声诈骗"],
    "老年": ["养老诈骗"],
    "养老": ["养老诈骗"],
    "信用卡": ["信用卡诈骗"],
    "两卡": ["两卡犯罪"],
    "跑分": ["跑分洗钱"],
    "客服": ["冒充客服诈骗"],
    "退款": ["退款诈骗"],
    "二维码": ["二维码诈骗"],
    "共享屏幕": ["屏幕共享"],
    "公检法": ["公检法诈骗"],
    "冻结": ["安全账户"],
    "反诈": ["反诈宣传"],
}

_CATEGORY_CASE_TOKENS = ["典型案例", "参考案例", "诈骗案", "帮助信息网络犯罪活动案", "被告人", "判决"]
_CATEGORY_LAW_TOKENS = ["中华人民共和国", "意见", "解释", "办法", "法律", "法规", "第.*条"]

# ── 候选正文选择器（按优先级排列）────────────────────────────────────────────

_CONTENT_SELECTORS = [
    "article",
    ".article-content",
    ".post-content",
    ".entry-content",
    "#content",
    ".content",
    ".main-content",
    "main",
    ".txt_txt",
    "#zoom",
    "#Zoom",
    "#UCAP-CONTENT .trs_editor_view",
    ".pages_content",
    ".detail-content",
    ".news-content",
    ".detail",
]

_TITLE_SELECTORS = [
    "h1",
    "h1.title",
    "h2.title",
    ".article-title",
    ".post-title",
    ".news-title",
    "title",
]


# ── 内部工具函数 ──────────────────────────────────────────────────────────────

def _text_of(node: Any) -> str:
    if node is None:
        return ""
    return clean_text(node.get_text(" ", strip=True))


def _extract_datetime(text: str) -> str | None:
    match = re.search(
        r"(\d{4}[-年/]\d{1,2}[-月/]\d{1,2}(?:日)?(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)",
        text,
    )
    if not match:
        return None
    value = match.group(1).strip()
    return value.replace("年", "-").replace("月", "-").replace("日", "")


def _infer_tags(title: str, content: str) -> list[str]:
    text = f"{title}\n{content}"
    tags: list[str] = []
    for keyword, values in _TAG_KEYWORDS.items():
        if keyword in text:
            tags.extend(values)
    return unique_preserve(tags)


def _guess_category(title: str, content: str) -> str:
    combined = f"{title}\n{content}"
    if any(t in combined for t in _CATEGORY_CASE_TOKENS):
        return "case"
    for token in _CATEGORY_LAW_TOKENS:
        if re.search(token, combined):
            return "law"
    return "article"


def _infer_subtype(text: str, category: str) -> str | None:
    if any(t in text for t in ["AI拟声", "换音"]):
        return "ai_voice_family_urgency"
    if any(t in text for t in ["招聘", "培训", "兼职"]):
        return "job_training_fraud"
    if any(t in text for t in ["投资", "黄金", "荐股", "理财"]):
        return "investment_fraud"
    if any(t in text for t in ["客服", "退款", "包裹", "理赔"]):
        return "customer_service_fraud"
    if any(t in text for t in ["信用卡"]):
        return "credit_card_fraud"
    if any(t in text for t in ["两卡", "跑分", "帮信"]):
        return "card_running_score"
    if category == "law":
        return "fraud_law"
    if category == "case":
        return "fraud_case"
    return None


def _extract_main_text(node: Any) -> str:
    if node is None:
        return ""
    lines: list[str] = []
    for para in node.find_all(["p", "div"], recursive=True):
        text = clean_text(para.get_text(" ", strip=True))
        if text:
            lines.append(text)
    if not lines:
        return clean_text(node.get_text("\n", strip=True))
    return "\n".join(unique_preserve(lines))


def _extract_images(node: Any, base_url: str) -> list[ImageAsset]:
    if node is None:
        return []
    assets: list[ImageAsset] = []
    for img in node.find_all("img"):
        src = img.get("src") or img.get("data-uploadpic") or img.get("data-src")
        if not src:
            continue
        full_url = urljoin(base_url, src) if base_url else src
        assets.append(
            ImageAsset(
                url=full_url,
                title=img.get("title", "") or img.get("alt", ""),
                caption="",
            )
        )
    return assets


def _extract_meta(soup: BeautifulSoup) -> tuple[str | None, str | None]:
    """尝试提取来源名称和发布时间。"""
    full_text = soup.get_text(" ", strip=True)
    published_at = _extract_datetime(full_text)

    source_name: str | None = None
    for pattern in [r"来源[:：]\s*([^\s\n,，。]{2,20})", r"发布单位[:：]\s*([^\s\n,，。]{2,20})"]:
        m = re.search(pattern, full_text)
        if m:
            source_name = m.group(1).strip()
            break

    return source_name, published_at


# ── 公开 API ──────────────────────────────────────────────────────────────────

def parse_html_file(
    html_path: str | Path,
    *,
    source_url: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
) -> list[KnowledgeDocument]:
    """
    解析本地 HTML 文件，提取诈骗案例文档。

    Args:
        html_path: HTML 文件路径
        source_url: 原始 URL（用于去重和图片解析），默认为 file:// 路径
        category: 强制指定分类 (law|case|article|photo_type)，None 则自动推断
        tags: 附加标签列表

    Returns:
        KnowledgeDocument 列表（通常 1 个，图片文章可能多个）
    """
    path = Path(html_path)
    html = path.read_text(encoding="utf-8", errors="replace")
    url = source_url or path.as_uri()
    return parse_html_content(html, source_url=url, category=category, tags=tags)


def parse_html_content(
    html: str,
    *,
    source_url: str = "",
    category: str | None = None,
    tags: list[str] | None = None,
) -> list[KnowledgeDocument]:
    """
    解析 HTML 字符串，提取诈骗案例文档。

    Args:
        html: HTML 原始字符串
        source_url: 原始 URL
        category: 强制指定分类，None 则自动推断
        tags: 附加标签列表

    Returns:
        KnowledgeDocument 列表
    """
    soup = BeautifulSoup(html, "html.parser")

    # ── 提取标题 ──────────────────────────────────────────
    title = ""
    for selector in _TITLE_SELECTORS:
        node = soup.select_one(selector)
        if node:
            title = _text_of(node)
            if title:
                break
    title = title or "未知标题"

    # ── 提取正文 ──────────────────────────────────────────
    content_node = None
    for selector in _CONTENT_SELECTORS:
        content_node = soup.select_one(selector)
        if content_node:
            break

    content = _extract_main_text(content_node)
    if not content:
        # 兜底：取 body 全部文本
        body = soup.find("body")
        content = clean_text(body.get_text("\n", strip=True) if body else soup.get_text("\n", strip=True))

    # ── 推断元数据 ────────────────────────────────────────
    source_name, published_at = _extract_meta(soup)
    inferred_category = category or _guess_category(title, content)
    inferred_tags = unique_preserve((tags or []) + _infer_tags(title, content))
    subtype = _infer_subtype(f"{title}\n{content}", inferred_category)

    # ── 解析来源站点 ──────────────────────────────────────
    source_site = "local_html"
    if source_url:
        parsed = urlparse(source_url)
        if parsed.netloc:
            source_site = parsed.netloc

    # ── 构建文档 ──────────────────────────────────────────
    canonical = canonicalize_url(source_url) if source_url else sha1_text(title, content[:120])
    doc_id = sha1_text(canonical, inferred_category, title)

    doc = KnowledgeDocument(
        doc_id=doc_id,
        url=source_url or f"local://{doc_id}",
        canonical_url=canonical or f"local://{doc_id}",
        source_site=source_site,
        category=inferred_category,
        title=clean_text(title),
        content=content,
        summary=build_summary(content),
        published_at=published_at,
        source_name=source_name,
        subtype=subtype,
        tags=inferred_tags,
        images=_extract_images(content_node, source_url),
        metadata={"import_source": "html_importer"},
    )
    return [doc]


def parse_html_directory(
    directory: str | Path,
    *,
    glob_pattern: str = "**/*.html",
    category: str | None = None,
    tags: list[str] | None = None,
) -> list[KnowledgeDocument]:
    """
    批量解析目录下所有 HTML 文件。

    Args:
        directory: 目录路径
        glob_pattern: 文件匹配模式
        category: 强制分类
        tags: 附加标签

    Returns:
        去重后的 KnowledgeDocument 列表
    """
    directory = Path(directory)
    docs: list[KnowledgeDocument] = []
    seen: set[str] = set()

    for html_file in sorted(directory.glob(glob_pattern)):
        try:
            for doc in parse_html_file(html_file, category=category, tags=tags):
                if doc.doc_id not in seen:
                    seen.add(doc.doc_id)
                    docs.append(doc)
        except Exception as exc:  # noqa: BLE001
            print(f"[html_importer] 跳过 {html_file.name}: {exc}")

    return docs

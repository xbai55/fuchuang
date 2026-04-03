"""
RAG 官方源爬虫
从人大网、最高法、政府网抓取反诈知识文档。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode, urljoin, urlsplit, urlunsplit

import yaml
from bs4 import BeautifulSoup, Tag

from src.brain.rag.config import RAGConfig, SearchSourceConfig, SeedUrlConfig
from src.brain.rag.http_client import fetch_json, fetch_text
from src.brain.rag.models import ImageAsset, KnowledgeDocument


GOV_ATHENA_ENDPOINT = (
    "https://sousuoht.www.gov.cn/athena/forward/"
    "2B22E8E39E850E17F95A016A74FCB6B673336FA8B6FEC0E2955907EF9AEE06BE"
)
GOV_ATHENA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Content-Type": "application/json;charset=utf-8",
    "athenaAppKey": (
        "cipgb8doyjEYO%2F1ImrWXzjTVEKS6%2FF2WJkaSqOKXCBnkTB2bYkn90nLHYZviLd5K2VSl8LEdgh3A4wwHQRmmC4Ar"
        "%2F102tJ%2BPflf3f5Yy8MZpd%2Bs%2Frxjf4hTAlzciSSAnsZ9W7CBLHbak9lOcoi7GMpPpg%2FD9md75FjL%2F%2Fl4O3Xs%3D"
    ),
    "athenaAppName": "%E5%9B%BD%E7%BD%91%E6%90%9C%E7%B4%A2",
}
NPC_SEARCH_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "http://www.npc.gov.cn/npc/c191/c12481/search/index.html",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}


def sha1_text(*parts: str) -> str:
    import hashlib

    digest = hashlib.sha1()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\x1f")
    return digest.hexdigest()


def canonicalize_url(url: str) -> str:
    split = urlsplit(url.strip())
    path = split.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urlunsplit(
        (
            split.scheme.lower() or "http",
            split.netloc.lower(),
            path,
            "",
            "",
        )
    )


def strip_html(text: str) -> str:
    if "<" not in text and ">" not in text:
        return text
    return BeautifulSoup(text, "html.parser").get_text(" ", strip=True)


def unique_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        item = item.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_text(text: str) -> str:
    text = normalize_whitespace(text)
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    return "\n".join(lines).strip()


def build_summary(text: str, limit: int = 160) -> str:
    text = clean_text(text)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def load_manual_photo_types(path: Path) -> list[KnowledgeDocument]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    docs: list[KnowledgeDocument] = []
    for item in raw.get("photo_types", []):
        title = item["title"]
        subtype = item.get("subtype")
        tags = list(item.get("tags", []))
        signals = item.get("risk_signals", [])
        content = "\n".join(
            [
                f"照片类型：{title}",
                f"说明：{item.get('description', '')}",
                f"风险信号：{'；'.join(signals)}",
                f"相关标签：{'、'.join(tags)}",
            ]
        )
        doc_id = sha1_text("manual-photo", title, subtype or "")
        docs.append(
            KnowledgeDocument(
                doc_id=doc_id,
                url=f"manual://photo-types/{doc_id}",
                canonical_url=f"manual://photo-types/{doc_id}",
                source_site="manual_seed",
                category="photo_type",
                title=title,
                content=clean_text(content),
                summary=build_summary(content),
                source_name="manual_seed",
                subtype=subtype,
                tags=tags,
            )
        )
    return docs


def collect_documents(config: RAGConfig) -> list[KnowledgeDocument]:
    documents: list[KnowledgeDocument] = []

    for seed in config.sources.seed_urls:
        documents.extend(parse_url(seed.url, override=seed))

    if config.sources.npc.enabled:
        for query in config.sources.npc.search_terms:
            for item in search_npc(query, config.sources.npc):
                documents.extend(
                    parse_url(
                        item["url"],
                        override=SeedUrlConfig(
                            url=item["url"],
                            category="law",
                            subtype=_infer_subtype(item["title"], "law"),
                            tags=_merge_tags(config.sources.npc.title_include, _infer_tags(item["title"], item["title"])),
                        ),
                    )
                )

    if config.sources.court.enabled:
        for query in config.sources.court.search_terms:
            for item in search_court(query, config.sources.court):
                category = _guess_category(item["title"], item.get("snippet", ""))
                documents.extend(
                    parse_url(
                        item["url"],
                        override=SeedUrlConfig(
                            url=item["url"],
                            category=category,
                            subtype=_infer_subtype(item["title"], category),
                            tags=_merge_tags(config.sources.court.title_include, _infer_tags(item["title"], item.get("snippet", ""))),
                        ),
                    )
                )

    if config.sources.gov_images.enabled:
        for query in config.sources.gov_images.search_terms:
            for item in search_gov_images(query, config.sources.gov_images):
                documents.extend(
                    parse_url(
                        item["url"],
                        override=SeedUrlConfig(
                            url=item["url"],
                            category="image_article",
                            subtype="official_image_article",
                            tags=_merge_tags(
                                config.sources.gov_images.title_include,
                                _infer_tags(item["title"], item.get("snippet", "")),
                            ),
                        ),
                    )
                )

    documents.extend(load_manual_photo_types(config.photo_types_seed_file))
    return deduplicate_documents(documents)


def deduplicate_documents(documents: list[KnowledgeDocument]) -> list[KnowledgeDocument]:
    output: list[KnowledgeDocument] = []
    seen: set[tuple[str, str]] = set()
    for doc in documents:
        key = (doc.canonical_url, doc.category)
        if key in seen:
            continue
        seen.add(key)
        output.append(doc)
    return output


def search_npc(query: str, config: SearchSourceConfig) -> list[dict[str, str]]:
    params = {
        "searchTag": 1,
        "allKeywords": query,
        "startTime": "",
        "endTime": "",
        "sort": "",
        "position": config.position,
        "pageNum": 1,
        "pageSize": config.page_size,
    }
    url = "http://www.npc.gov.cn/search?" + urlencode(params)
    payload = fetch_json(url, headers=NPC_SEARCH_HEADERS)
    rows = payload.get("data", {}).get("data", [])
    results: list[dict[str, str]] = []
    for row in rows:
        title = strip_html(row.get("title") or row.get("news_doctitle", ""))
        content = strip_html(row.get("news_doccontent", ""))
        if config.title_include and not any(token in title or token in content for token in config.title_include):
            continue
        results.append(
            {
                "title": title,
                "url": row.get("docpuburl", ""),
                "snippet": content,
            }
        )
    return _unique_results(results)


def search_court(query: str, config: SearchSourceConfig) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for page in range(1, config.max_pages_per_query + 1):
        url = f"https://www.court.gov.cn/search.html?content={quote(query)}&page={page}"
        html = fetch_text(url)
        soup = BeautifulSoup(html, "html.parser")
        items = soup.select(".search_list ul li")
        if not items:
            break

        for item in items:
            anchor = item.find("a")
            if not anchor or not anchor.get("href"):
                continue
            title = strip_html(anchor.get_text(" ", strip=True))
            snippet = clean_text(item.find("span").get_text(" ", strip=True) if item.find("span") else "")
            if config.title_include and not any(token in title for token in config.title_include):
                continue
            results.append(
                {
                    "title": title,
                    "url": urljoin("https://www.court.gov.cn", anchor["href"]),
                    "snippet": snippet,
                }
            )
    return _unique_results(results)


def search_gov_images(query: str, config: SearchSourceConfig) -> list[dict[str, str]]:
    body = {
        "code": "17da70961a7",
        "dataTypeId": "16",
        "orderBy": "time",
        "searchBy": "all",
        "appendixType": "",
        "granularity": "ALL",
        "trackTotalHits": True,
        "beginDateTime": "",
        "endDateTime": "",
        "isSearchForced": 0,
        "filters": [],
        "pageNo": 1,
        "pageSize": config.page_size,
        "searchWord": query,
    }
    payload = _post_json(GOV_ATHENA_ENDPOINT, body, headers=GOV_ATHENA_HEADERS)
    rows = payload.get("result", {}).get("data", {}).get("middle", {}).get("list", [])
    results: list[dict[str, str]] = []
    for row in rows:
        title = strip_html(row.get("title_no_tag") or row.get("title", ""))
        snippet = strip_html(row.get("content", "") or row.get("summary", ""))
        if config.title_include and not any(token in title or token in snippet for token in config.title_include):
            continue
        results.append(
            {
                "title": title,
                "url": row.get("url", ""),
                "snippet": snippet,
            }
        )
    return _unique_results(results)


def _post_json(url: str, data: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    from urllib.request import Request, urlopen

    request = Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8", "ignore"))


def _unique_results(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    output: list[dict[str, str]] = []
    for item in items:
        normalized = canonicalize_url(item["url"])
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(item)
    return output


def parse_url(url: str, override: SeedUrlConfig | None = None) -> list[KnowledgeDocument]:
    html = fetch_text(url)
    if "court.gov.cn" in url:
        return _parse_court_page(url, html, override)
    if "npc.gov.cn" in url:
        return _parse_npc_page(url, html, override)
    return _parse_gov_page(url, html, override)


def _parse_court_page(url: str, html: str, override: SeedUrlConfig | None) -> list[KnowledgeDocument]:
    soup = BeautifulSoup(html, "html.parser")
    title = _text_of(soup.select_one(".detail .title")) or _text_of(soup.find("title"))
    content_node = soup.select_one(".txt_txt") or soup.select_one("#zoom")
    content = _extract_main_text(content_node)
    source_name, published_at = _extract_court_meta(soup)
    category = override.category if override else _guess_category(title, content)
    tags = _merge_tags(override.tags if override else [], _infer_tags(title, content))
    subtype = override.subtype if override else _infer_subtype(title, category)

    doc = _make_document(
        url=url,
        source_site="court.gov.cn",
        source_name=source_name,
        category=category,
        title=title,
        content=content,
        published_at=published_at,
        subtype=subtype,
        tags=tags,
        images=_extract_images(content_node, url),
        metadata={"site": "court"},
    )
    return [doc]


def _parse_npc_page(url: str, html: str, override: SeedUrlConfig | None) -> list[KnowledgeDocument]:
    soup = BeautifulSoup(html, "html.parser")
    title = _text_of(soup.find("h1")) or _text_of(soup.find("title"))
    subtitle = _text_of(soup.find("h3"))
    content_node = soup.select_one("#Zoom")
    content = _extract_main_text(content_node)
    if subtitle:
        content = f"{subtitle}\n{content}" if content else subtitle

    meta_node = soup.select_one(".fontsize")
    meta_text = clean_text(meta_node.get_text(" ", strip=True) if meta_node else "")
    published_at = _extract_datetime(meta_text) or _text_of(soup.select_one("#zzrq"))

    category = override.category if override else _guess_category(title, content)
    tags = _merge_tags(override.tags if override else [], _infer_tags(title, content))
    subtype = override.subtype if override else _infer_subtype(title, category)

    doc = _make_document(
        url=url,
        source_site="npc.gov.cn",
        source_name="中国人大网",
        category=category,
        title=title,
        content=content,
        published_at=published_at,
        subtype=subtype,
        tags=tags,
        images=_extract_images(content_node, url),
        metadata={"site": "npc"},
    )
    return [doc]


def _parse_gov_page(url: str, html: str, override: SeedUrlConfig | None) -> list[KnowledgeDocument]:
    soup = BeautifulSoup(html, "html.parser")
    title = _text_of(soup.select_one("h1#ti")) or _text_of(soup.find("title"))
    content_node = soup.select_one("#UCAP-CONTENT .trs_editor_view") or soup.select_one(".pages_content")
    content = _extract_main_text(content_node)
    source_name, published_at = _extract_gov_meta(soup)

    category = override.category if override else _guess_category(title, content)
    tags = _merge_tags(override.tags if override else [], _infer_tags(title, content))
    subtype = override.subtype if override else _infer_subtype(title, category)

    docs = [
        _make_document(
            url=url,
            source_site="gov.cn",
            source_name=source_name,
            category=category,
            title=title,
            content=content,
            published_at=published_at,
            subtype=subtype,
            tags=tags,
            images=_extract_images(content_node, url),
            metadata={"site": "gov"},
        )
    ]

    docs.extend(_extract_gov_image_documents(url, title, content_node, source_name, published_at, tags))
    return docs


def _extract_gov_image_documents(
    url: str,
    title: str,
    content_node: Tag | None,
    source_name: str | None,
    published_at: str | None,
    base_tags: list[str],
) -> list[KnowledgeDocument]:
    if content_node is None:
        return []

    docs: list[KnowledgeDocument] = []
    current_image: ImageAsset | None = None
    current_lines: list[str] = []
    counter = 0

    def flush() -> None:
        nonlocal counter, current_image, current_lines
        if current_image is None:
            return

        caption = clean_text("\n".join(current_lines))
        if caption:
            counter += 1
            tags = _merge_tags(base_tags, _infer_tags(title, caption), ["图片说明", "照片类型"])
            docs.append(
                _make_document(
                    url=current_image.url or f"{canonicalize_url(url)}#image-{counter}",
                    source_site="gov.cn",
                    source_name=source_name,
                    category="photo_type",
                    title=f"{title} 图像{counter}",
                    content=f"图像标题：{title}\n图片说明：{caption}",
                    published_at=published_at,
                    subtype=_infer_subtype(caption, "photo_type"),
                    tags=tags,
                    images=[current_image],
                    metadata={
                        "site": "gov",
                        "image_index": counter,
                        "page_url": canonicalize_url(url),
                    },
                )
            )

        current_image = None
        current_lines = []

    for paragraph in content_node.find_all("p"):
        image = paragraph.find("img")
        text = clean_text(paragraph.get_text(" ", strip=True))
        if image and image.get("src"):
            flush()
            current_image = ImageAsset(
                url=urljoin(url, image.get("src")),
                title=image.get("title", "") or image.get("alt", ""),
                caption="",
            )
            continue

        if current_image and text:
            current_lines.append(text)

    flush()
    return docs


def _make_document(
    *,
    url: str,
    source_site: str,
    source_name: str | None,
    category: str,
    title: str,
    content: str,
    published_at: str | None,
    subtype: str | None,
    tags: list[str],
    images: list[ImageAsset],
    metadata: dict[str, Any],
) -> KnowledgeDocument:
    content = clean_text(content)
    canonical_url = canonicalize_url(url)
    doc_id = sha1_text(canonical_url, category, title)
    return KnowledgeDocument(
        doc_id=doc_id,
        url=url,
        canonical_url=canonical_url,
        source_site=source_site,
        category=category,
        title=clean_text(title),
        content=content,
        summary=build_summary(content),
        published_at=published_at,
        source_name=source_name,
        subtype=subtype,
        tags=unique_preserve(tags),
        images=images,
        metadata=metadata,
    )


def _extract_main_text(node: Tag | None) -> str:
    if node is None:
        return ""

    lines: list[str] = []
    for paragraph in node.find_all(["p", "div"], recursive=True):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if text:
            lines.append(text)

    if not lines:
        return clean_text(node.get_text("\n", strip=True))
    return "\n".join(unique_preserve(lines))


def _extract_images(node: Tag | None, base_url: str) -> list[ImageAsset]:
    if node is None:
        return []

    assets: list[ImageAsset] = []
    for image in node.find_all("img"):
        source = image.get("src") or image.get("data-uploadpic")
        if not source:
            continue
        assets.append(
            ImageAsset(
                url=urljoin(base_url, source),
                title=image.get("title", "") or image.get("alt", ""),
                caption="",
            )
        )
    return assets


def _extract_court_meta(soup: BeautifulSoup) -> tuple[str | None, str | None]:
    source_name = None
    published_at = None
    for item in soup.select(".detail_mes .message li"):
        text = clean_text(item.get_text(" ", strip=True))
        if "来源" in text:
            source_name = text.split("：", 1)[-1].strip()
        if "发布时间" in text:
            published_at = text.split("：", 1)[-1].strip()
    return source_name, published_at


def _extract_gov_meta(soup: BeautifulSoup) -> tuple[str | None, str | None]:
    source_name = None
    published_at = None
    node = soup.select_one(".pages-date")
    if not node:
        return None, None

    text = clean_text(node.get_text("\n", strip=True))
    published_at = _extract_datetime(text)
    source_match = re.search(r"来源[:：]\s*([^\n]+)", text)
    if source_match:
        source_name = source_match.group(1).strip()
    return source_name, published_at


def _extract_datetime(text: str) -> str | None:
    match = re.search(r"(\d{4}[-年/]\d{1,2}[-月/]\d{1,2}(?:日)?(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)", text)
    if not match:
        return None
    value = match.group(1).strip()
    return value.replace("年", "-").replace("月", "-").replace("日", "")


def _text_of(node: Tag | None) -> str:
    return clean_text(node.get_text(" ", strip=True) if node else "")


def _guess_category(title: str, content: str) -> str:
    text = f"{title}\n{content}"
    if any(token in text for token in ["法律", "条例", "司法", "意见", "刑法"]):
        return "law"
    if any(token in text for token in ["案例", "案情", "判决", "诈骗"]):
        return "case"
    return "image_article"


def _infer_subtype(title: str, category: str) -> str | None:
    text = title.lower()
    if category == "law":
        if "反电信" in title:
            return "anti_telecom_fraud_law"
        if "266" in title or "第二百六十六" in title:
            return "fraud_article_266_interpretation"
        return "general_fraud_law"

    if "刷单" in text or "兼职" in text:
        return "part_time_fraud"
    if "投资" in text or "理财" in text:
        return "investment_fraud"
    if "客服" in text or "退款" in text:
        return "customer_service_fraud"
    if "公检法" in text:
        return "authority_impersonation_fraud"
    if "二维码" in text:
        return "qr_code_fraud"
    if "两卡" in text:
        return "two_card_crime"
    if category == "photo_type":
        return "photo_risk_pattern"
    return None


def _infer_tags(title: str, content: str) -> list[str]:
    text = f"{title}\n{content}"
    tags: list[str] = []
    mapping = {
        "电信": "电信诈骗",
        "诈骗": "诈骗",
        "反诈": "反诈",
        "投资": "投资诈骗",
        "客服": "客服诈骗",
        "退款": "退款诈骗",
        "公检法": "冒充公检法",
        "二维码": "二维码诈骗",
        "两卡": "两卡犯罪",
        "截图": "图片证据",
    }
    for keyword, tag in mapping.items():
        if keyword in text:
            tags.append(tag)
    return unique_preserve(tags)


def _merge_tags(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    for group in groups:
        merged.extend(group)
    return unique_preserve(merged)

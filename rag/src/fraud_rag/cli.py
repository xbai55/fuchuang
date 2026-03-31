from __future__ import annotations

import argparse
import json

from .config import load_config
from .detector import assess_risk
from .pipeline import build_all, build_chunks, crawl_documents, load_index


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="诈骗知识库构建与检索工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    crawl = subparsers.add_parser("crawl", help="抓取并保存知识文档")
    crawl.add_argument("--config", default="configs/sources.example.yaml")

    build = subparsers.add_parser("build", help="抓取、分块并构建向量索引")
    build.add_argument("--config", default="configs/sources.example.yaml")
    build.add_argument("--backend", choices=["tfidf", "sentence-transformer"], default=None)

    query = subparsers.add_parser("query", help="执行相似检索")
    query.add_argument("--index-dir", default="artifacts/index")
    query.add_argument("--text", required=True)
    query.add_argument("--top-k", type=int, default=5)

    warn = subparsers.add_parser("warn", help="执行诈骗风险预警")
    warn.add_argument("--config", default="configs/sources.example.yaml")
    warn.add_argument("--index-dir", default="artifacts/index")
    warn.add_argument("--text", default="")
    warn.add_argument("--image-text", default="")
    warn.add_argument("--ocr-text", default="")
    warn.add_argument("--top-k", type=int, default=5)

    chunks = subparsers.add_parser("chunk", help="对现有文档执行分块")
    chunks.add_argument("--config", default="configs/sources.example.yaml")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "crawl":
        config = load_config(args.config)
        rows = crawl_documents(config)
        print(json.dumps({"documents": len(rows), "output": str(config.paths.raw_documents)}, ensure_ascii=False, indent=2))
        return

    if args.command == "chunk":
        config = load_config(args.config)
        chunks = build_chunks(config)
        print(json.dumps({"chunks": len(chunks), "output": str(config.paths.chunks)}, ensure_ascii=False, indent=2))
        return

    if args.command == "build":
        config = load_config(args.config)
        stats = build_all(config, backend=args.backend)
        stats["index_dir"] = str(config.paths.index_dir)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return

    if args.command == "query":
        index = load_index(args.index_dir)
        hits = index.search(args.text, top_k=args.top_k)
        print(
            json.dumps(
                {
                    "query": args.text,
                    "hits": [hit.to_dict() for hit in hits],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if args.command == "warn":
        config = load_config(args.config)
        index = load_index(args.index_dir)
        query_text = "\n".join(part for part in [args.text, args.image_text, args.ocr_text] if part.strip())
        hits = index.search(query_text, top_k=args.top_k)
        result = assess_risk(query_text, hits, config.warning)
        result["query"] = {
            "text": args.text,
            "image_text": args.image_text,
            "ocr_text": args.ocr_text,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return


if __name__ == "__main__":
    main()

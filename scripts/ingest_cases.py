"""
Fraud case ingestion CLI.

Usage:
  python scripts/ingest_cases.py --file data/cases.csv --source my_batch
  python scripts/ingest_cases.py --file data/cases.json --source gov_2024 --no-enrich
  python scripts/ingest_cases.py --file data/page.html --source web_scrape
  python scripts/ingest_cases.py --url https://example.com/case/123 --source web_live
  python scripts/ingest_cases.py --url-list data/urls.txt --source bulk_scrape --delay 2.0

Input formats:
  CSV    columns: text (required), id (optional). Also accepts Chinese headers: 内容/案例, 编号
  JSON   list of {"id": "...", "text": "..."} OR JSONL
  HTML   local file; auto-detects list pages vs. single-case detail pages
  URL    live fetch + HTML parse
  URL list  plain-text file, one URL per line, # for comments

Flags:
  --no-enrich    skip LLM enrichment (fast, tags will be empty)
  --dry-run      print stats without writing to DB
  --delay N      seconds between URL fetches (default 1.5)
"""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
sys.path.insert(0, str(Path(__file__).parent))

from etl.cleaner import clean, text_hash
from etl.enricher import enrich
from etl.html_parser import parse_html_file, parse_html
from etl.scraper import fetch_url, fetch_urls, load_url_list
from database import SessionLocal, FraudCase, init_db


def load_records(file_path: str) -> list[dict]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    records = []
    if path.suffix == ".csv":
        with open(path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                text = row.get("text") or row.get("内容") or row.get("案例") or ""
                source_id = str(row.get("id") or row.get("编号") or "")
                records.append({"text": text, "source_id": source_id})

    elif path.suffix in (".json", ".jsonl"):
        with open(path, encoding="utf-8") as f:
            content = f.read().strip()
        try:
            data = json.loads(content)
            if isinstance(data, list):
                records = [{"text": str(d.get("text", "")), "source_id": str(d.get("id", ""))} for d in data]
            else:
                records = [{"text": str(data.get("text", "")), "source_id": str(data.get("id", ""))}]
        except json.JSONDecodeError:
            for line in content.splitlines():
                line = line.strip()
                if line:
                    d = json.loads(line)
                    records.append({"text": str(d.get("text", "")), "source_id": str(d.get("id", ""))})

    elif path.suffix in (".html", ".htm"):
        records = parse_html_file(str(path))

    else:
        raise ValueError(f"Unsupported format: {path.suffix}. Use .csv, .json, .jsonl, .html, or .htm")

    return records


def load_records_from_urls(urls: list[str], delay: float) -> list[dict]:
    """Fetch URLs and parse HTML; returns combined record list."""
    html_map = fetch_urls(urls, delay=delay) if len(urls) > 1 else {urls[0]: fetch_url(urls[0])}
    records = []
    for url, html in html_map.items():
        if html is None:
            print(f"  SKIP (fetch failed): {url}")
            continue
        parsed = parse_html(html, source_prefix=url.split("/")[-1] or "page", url=url)
        records.extend(parsed)
        print(f"  Parsed {len(parsed)} record(s) from {url}")
    return records


def run(records: list[dict], source: str, do_enrich: bool, dry_run: bool):
    init_db()
    print(f"Processing {len(records)} records")

    stats = {"total": len(records), "inserted": 0, "skipped_clean": 0, "skipped_dup": 0}

    db = SessionLocal()
    try:
        for i, rec in enumerate(records, 1):
            raw = rec["text"]
            source_id = rec.get("source_id") or f"{source}_{i}"

            try:
                cleaned = clean(raw)
            except ValueError as e:
                print(f"  [{i}] SKIP clean: {e}")
                stats["skipped_clean"] += 1
                continue

            h = text_hash(cleaned)
            if db.query(FraudCase).filter_by(text_hash=h).first():
                print(f"  [{i}] SKIP dup: hash {h[:12]}...")
                stats["skipped_dup"] += 1
                continue

            if db.query(FraudCase).filter_by(source_id=source_id).first():
                print(f"  [{i}] SKIP dup: source_id {source_id}")
                stats["skipped_dup"] += 1
                continue

            enrichment = (
                enrich(cleaned) if do_enrich
                else {"scam_type": "", "risk_keywords": [], "legal_references": "", "severity": "medium"}
            )

            if dry_run:
                print(f"  [{i}] DRY-RUN: scam_type={enrichment['scam_type']} severity={enrichment['severity']}")
                stats["inserted"] += 1
                continue

            case = FraudCase(
                source=source,
                source_id=source_id,
                raw_text=raw,
                cleaned_text=cleaned,
                scam_type=enrichment["scam_type"],
                risk_keywords=json.dumps(enrichment["risk_keywords"], ensure_ascii=False),
                legal_references=enrichment["legal_references"],
                severity=enrichment["severity"],
                text_hash=h,
                is_synced=False,
            )
            db.add(case)
            db.commit()
            stats["inserted"] += 1
            print(f"  [{i}] OK: {enrichment['scam_type']} / {enrichment['severity']}")

    finally:
        db.close()

    print("\n--- Summary ---")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest fraud cases into database")

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--file", help="Path to CSV/JSON/JSONL/HTML source file")
    input_group.add_argument("--url", help="Single URL to fetch and parse")
    input_group.add_argument("--url-list", help="Plain-text file with one URL per line")

    parser.add_argument("--source", required=True, help="Source identifier tag (e.g. 'gov_2024')")
    parser.add_argument("--no-enrich", action="store_true", help="Skip LLM enrichment")
    parser.add_argument("--dry-run", action="store_true", help="Print stats without writing")
    parser.add_argument("--delay", type=float, default=1.5, help="Seconds between URL fetches (default 1.5)")
    args = parser.parse_args()

    if args.file:
        records = load_records(args.file)
    elif args.url:
        records = load_records_from_urls([args.url], delay=args.delay)
    else:
        urls = load_url_list(args.url_list)
        print(f"Loaded {len(urls)} URLs from {args.url_list}")
        records = load_records_from_urls(urls, delay=args.delay)

    run(
        records=records,
        source=args.source,
        do_enrich=not args.no_enrich,
        dry_run=args.dry_run,
    )

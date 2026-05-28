from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import feedparser
import requests
from dateutil import parser as date_parser
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"


ARXIV_QUERY = (
    '(ti:"embodied" OR abs:"embodied" OR '
    'ti:"robot learning" OR abs:"robot learning" OR '
    'ti:"vision-language-action" OR abs:"vision-language-action" OR '
    'ti:"VLA" OR abs:"VLA" OR '
    'ti:"humanoid" OR abs:"humanoid" OR '
    'ti:"diffusion policy" OR abs:"diffusion policy" OR '
    'ti:"sim2real" OR abs:"sim2real" OR '
    'ti:"robot foundation model" OR abs:"robot foundation model") '
    "AND (cat:cs.RO OR cat:cs.AI OR cat:cs.CV OR cat:cs.LG)"
)


def _to_iso(value: datetime | None) -> str | None:
    """把时间转换成稳定的 ISO 字符串。"""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _clean_text(value: str | None) -> str:
    """清理 arXiv 返回文本中的多余空白。"""
    return " ".join((value or "").split())


def _parse_datetime(value: str | None) -> datetime | None:
    """解析 arXiv Atom feed 中的时间字段。"""
    if not value:
        return None
    try:
        parsed = date_parser.parse(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _pdf_url(entry: dict[str, Any]) -> str | None:
    """从 arXiv Atom 链接中提取 PDF 地址。"""
    for link in entry.get("links", []):
        if link.get("type") == "application/pdf":
            return link.get("href")
    return None


def _entry_to_dict(entry: dict[str, Any]) -> dict[str, Any]:
    """把 arXiv Atom 条目转换为可持久化的字典。"""
    published = _parse_datetime(entry.get("published"))
    updated = _parse_datetime(entry.get("updated"))
    authors = [author.get("name") for author in entry.get("authors", []) if author.get("name")]
    categories = [tag.get("term") for tag in entry.get("tags", []) if tag.get("term")]
    primary_category = ""
    if isinstance(entry.get("arxiv_primary_category"), dict):
        primary_category = entry.get("arxiv_primary_category", {}).get("term", "")
    return {
        "source": "arXiv",
        "id": entry.get("id"),
        "title": _clean_text(entry.get("title")),
        "abstract": _clean_text(entry.get("summary")),
        "authors": authors,
        "published": _to_iso(published),
        "updated": _to_iso(updated),
        "url": entry.get("id"),
        "pdf_url": _pdf_url(entry),
        "categories": categories,
        "primary_category": primary_category,
    }


def collect_papers(
    target_date: date | None = None,
    max_results: int | None = None,
    days: int = 3,
) -> list[dict[str, Any]]:
    """从 arXiv API 采集具身智能相关论文。"""
    load_dotenv(ROOT / ".env")
    target_date = target_date or date.today()
    max_results = max_results or int(os.getenv("ARXIV_MAX_RESULTS", "20"))
    since = datetime.combine(target_date - timedelta(days=days), datetime.min.time()).replace(
        tzinfo=timezone.utc
    )

    response = requests.get(
        "https://export.arxiv.org/api/query",
        params={
            "search_query": ARXIV_QUERY,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        },
        headers={"User-Agent": "embodied-ai-daily/0.1"},
        timeout=30,
    )
    if response.status_code == 429:
        raise RuntimeError("arXiv API 当前限流，请稍后重试。")
    response.raise_for_status()
    parsed = feedparser.parse(response.text)

    papers: list[dict[str, Any]] = []
    for entry in parsed.entries:
        published = _parse_datetime(entry.get("published"))
        if published and published < since:
            continue
        papers.append(_entry_to_dict(entry))

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    output = RAW_DIR / f"papers_{target_date.isoformat()}.json"
    output.write_text(json.dumps(papers, ensure_ascii=False, indent=2), encoding="utf-8")
    return papers


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="采集具身智能相关 arXiv 论文")
    parser.add_argument("--date", type=str, default=date.today().isoformat(), help="日报日期")
    parser.add_argument("--max-results", type=int, default=None, help="最大论文数量")
    parser.add_argument("--days", type=int, default=3, help="向前回看天数")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date)
    papers = collect_papers(target_date=target_date, max_results=args.max_results, days=args.days)
    print(f"已采集论文 {len(papers)} 篇")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import feedparser
from dateutil import parser as date_parser
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"


DEFAULT_FEEDS = [
    "https://www.therobotreport.com/feed/",
    "https://spectrum.ieee.org/feeds/topic/robotics.rss",
    "https://news.mit.edu/rss/topic/robotics",
    "https://blogs.nvidia.com/blog/category/industries/robotics/feed/",
    "https://deepmind.google/blog/rss.xml",
    "https://huggingface.co/blog/feed.xml",
]


KEYWORDS = [
    "embodied",
    "robot",
    "robotics",
    "humanoid",
    "manipulation",
    "foundation model",
    "vision-language-action",
    "vla",
    "diffusion policy",
    "sim2real",
    "warehouse automation",
    "autonomous",
]


def _parse_date(entry: dict[str, Any]) -> datetime | None:
    """尽量从 RSS 条目中解析发布时间。"""
    raw_value = entry.get("published") or entry.get("updated") or entry.get("created")
    if not raw_value:
        return None
    try:
        parsed = date_parser.parse(raw_value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _match_keywords(text: str) -> bool:
    """用关键词筛选具身智能相关动态。"""
    lower_text = text.lower()
    return any(keyword in lower_text for keyword in KEYWORDS)


def _entry_to_dict(feed_url: str, entry: dict[str, Any]) -> dict[str, Any]:
    """把 RSS 条目转换为统一结构。"""
    published_at = _parse_date(entry)
    summary = " ".join((entry.get("summary") or "").split())
    return {
        "source": "RSS",
        "feed_url": feed_url,
        "feed_title": entry.get("source", {}).get("title") if isinstance(entry.get("source"), dict) else "",
        "title": " ".join((entry.get("title") or "").split()),
        "summary": summary,
        "url": entry.get("link"),
        "published": published_at.isoformat() if published_at else None,
    }


def _feed_urls_from_env() -> list[str]:
    """读取用户追加的 RSS 源。"""
    custom = os.getenv("NEWS_RSS_FEEDS", "")
    custom_feeds = [item.strip() for item in custom.split(",") if item.strip()]
    return [*DEFAULT_FEEDS, *custom_feeds]


def collect_news(
    target_date: date | None = None,
    max_results: int | None = None,
    days: int = 7,
) -> list[dict[str, Any]]:
    """从 RSS feeds 采集行业和公司动态。"""
    load_dotenv(ROOT / ".env")
    target_date = target_date or date.today()
    max_results = max_results or int(os.getenv("NEWS_MAX_RESULTS", "20"))
    since = datetime.combine(target_date - timedelta(days=days), datetime.min.time()).replace(
        tzinfo=timezone.utc
    )

    news: dict[str, dict[str, Any]] = {}
    for feed_url in _feed_urls_from_env():
        parsed = feedparser.parse(feed_url)
        for entry in parsed.entries:
            text = f"{entry.get('title', '')} {entry.get('summary', '')}"
            if not _match_keywords(text):
                continue
            published_at = _parse_date(entry)
            if published_at and published_at < since:
                continue
            item = _entry_to_dict(feed_url, entry)
            if item["url"]:
                news[item["url"]] = item

    result = sorted(news.values(), key=lambda item: item.get("published") or "", reverse=True)[:max_results]

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    output = RAW_DIR / f"news_{target_date.isoformat()}.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="采集具身智能行业和公司动态")
    parser.add_argument("--date", type=str, default=date.today().isoformat(), help="日报日期")
    parser.add_argument("--max-results", type=int, default=None, help="最大动态数量")
    parser.add_argument("--days", type=int, default=7, help="向前回看天数")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date)
    news = collect_news(target_date=target_date, max_results=args.max_results, days=args.days)
    print(f"已采集行业动态 {len(news)} 条")


if __name__ == "__main__":
    main()

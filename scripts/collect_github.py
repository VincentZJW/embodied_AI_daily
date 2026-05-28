from __future__ import annotations

import argparse
import base64
import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"


QUERIES = [
    '"embodied ai" robot',
    '"vision language action" robot',
    '"VLA" robot learning',
    '"diffusion policy" robot',
    '"humanoid robot" learning',
    '"sim2real" robotics',
    '"robot foundation model"',
]


def _headers() -> dict[str, str]:
    """构造 GitHub API 请求头。"""
    token = os.getenv("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "embodied-ai-daily",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_readme(session: requests.Session, full_name: str) -> tuple[str, str]:
    """通过 GitHub REST API 拉取仓库 README 的原始文本。"""
    if not full_name:
        return "", ""
    response = session.get(
        f"https://api.github.com/repos/{full_name}/readme",
        headers={**_headers(), "Accept": "application/vnd.github+json"},
        timeout=30,
    )
    if response.status_code in {403, 404}:
        return "", ""
    response.raise_for_status()
    data = response.json()
    content = data.get("content", "")
    if data.get("encoding") == "base64":
        readme_text = base64.b64decode(content).decode("utf-8", errors="replace")
    else:
        readme_text = content
    readme_url = data.get("html_url") or f"https://github.com/{full_name}#readme"
    return readme_text[:5000], readme_url


def _repo_to_dict(item: dict[str, Any], readme_text: str = "", readme_url: str = "") -> dict[str, Any]:
    """只保留日报需要的仓库字段。"""
    return {
        "source": "GitHub",
        "id": item.get("id"),
        "name": item.get("name"),
        "full_name": item.get("full_name"),
        "description": item.get("description") or "",
        "html_url": item.get("html_url"),
        "stars": item.get("stargazers_count", 0),
        "forks": item.get("forks_count", 0),
        "language": item.get("language"),
        "topics": item.get("topics", []),
        "readme_text": readme_text,
        "readme_url": readme_url,
        "updated_at": item.get("updated_at"),
        "pushed_at": item.get("pushed_at"),
        "created_at": item.get("created_at"),
    }


def collect_github(
    target_date: date | None = None,
    max_results: int | None = None,
    days: int = 7,
) -> list[dict[str, Any]]:
    """通过 GitHub REST API 搜索近期活跃的具身智能项目。"""
    load_dotenv(ROOT / ".env")
    target_date = target_date or date.today()
    max_results = max_results or int(os.getenv("GITHUB_MAX_RESULTS", "20"))
    pushed_after = (target_date - timedelta(days=days)).isoformat()
    per_query = max(3, min(10, max_results))

    session = requests.Session()
    session.headers.update(_headers())

    repos: dict[str, dict[str, Any]] = {}
    for query in QUERIES:
        params = {
            "q": f"{query} pushed:>={pushed_after}",
            "sort": "stars",
            "order": "desc",
            "per_page": per_query,
        }
        response = session.get("https://api.github.com/search/repositories", params=params, timeout=30)
        if response.status_code == 403:
            raise RuntimeError("GitHub API 限额不足，请配置 GITHUB_TOKEN 后重试。")
        response.raise_for_status()
        for item in response.json().get("items", []):
            repo = _repo_to_dict(item)
            if repo["full_name"]:
                repos[repo["full_name"]] = repo

    result = sorted(repos.values(), key=lambda repo: repo.get("stars", 0), reverse=True)[:max_results]
    for repo in result:
        readme_text, readme_url = _fetch_readme(session, repo.get("full_name") or "")
        repo["readme_text"] = readme_text
        repo["readme_url"] = readme_url

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    output = RAW_DIR / f"github_{target_date.isoformat()}.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="采集具身智能相关 GitHub 项目")
    parser.add_argument("--date", type=str, default=date.today().isoformat(), help="日报日期")
    parser.add_argument("--max-results", type=int, default=None, help="最大项目数量")
    parser.add_argument("--days", type=int, default=7, help="向前回看天数")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date)
    repos = collect_github(target_date=target_date, max_results=args.max_results, days=args.days)
    print(f"已采集 GitHub 项目 {len(repos)} 个")


if __name__ == "__main__":
    main()

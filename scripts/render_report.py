from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Callable

from jinja2 import Template

try:
    from .collect_github import collect_github
    from .collect_news import collect_news
    from .collect_papers import collect_papers
    from .summarize import DailySummary, summarize
except ImportError:
    from collect_github import collect_github
    from collect_news import collect_news
    from collect_papers import collect_papers
    from summarize import DailySummary, summarize


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"
RAW_DIR = ROOT / "data" / "raw"


REPORT_TEMPLATE = """# 具身智能中文日报（{{ summary.date }}）

> 本日报由自动化系统生成。英文论文、报告、网页和 README 会在摘要阶段先理解，再转写为中文；必要英文技术术语会保留并配中文解释。

## 今日核心结论

{% for item in summary.core_conclusions %}
- {{ item }}
{% else %}
- 今日没有采集到足够信息，建议检查网络、API Key 或数据源配置。
{% endfor %}

## 重点论文

{% for paper in summary.papers %}
### {{ paper.title_zh }}

- 关注原因：{{ paper.reason }}
{% for highlight in paper.highlights %}
- 要点：{{ highlight }}
{% endfor %}
- 来源：{{ paper.url }}
{% else %}
- 今日没有采集到符合条件的重点论文。
{% endfor %}

## 重点 GitHub 项目

{% for project in summary.github_projects %}
### {{ project.name }}

- 中文摘要：{{ project.summary }}
- 跟踪价值：{{ project.why_follow }}
- 来源：{{ project.url }}
{% else %}
- 今日没有采集到符合条件的 GitHub 项目。
{% endfor %}

## 行业/公司动态

{% for item in summary.news %}
### {{ item.title_zh }}

- 中文摘要：{{ item.summary }}
- 影响判断：{{ item.impact }}
- 来源：{{ item.url }}
{% else %}
- 今日没有采集到符合条件的行业或公司动态。
{% endfor %}

## 技术词汇解释

{% for term in summary.terms %}
- **{{ term.term }}**：{{ term.explanation }}
{% else %}
- 暂无新增术语。
{% endfor %}

## 对猎头/招聘的启发

{% for item in summary.recruiting_insights %}
- {{ item }}
{% else %}
- 暂无招聘启发。
{% endfor %}

## 来源链接

{% for source in summary.sources %}
- [{{ source.type }}] {{ source.name }}：{{ source.url }}
{% else %}
- 暂无来源链接。
{% endfor %}
"""


def _save_collect_error(target_date: date, source: str, error: Exception) -> None:
    """记录采集失败原因，避免单个来源失败导致整份日报中断。"""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    output = RAW_DIR / f"errors_{target_date.isoformat()}.json"
    if output.exists():
        errors = json.loads(output.read_text(encoding="utf-8"))
    else:
        errors = []
    errors.append({"source": source, "error": str(error)})
    output.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_empty_raw(target_date: date, raw_name: str) -> None:
    """采集失败时写入空数组，避免复用同日期旧数据。"""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    output = RAW_DIR / f"{raw_name}_{target_date.isoformat()}.json"
    output.write_text("[]\n", encoding="utf-8")


def _safe_collect(
    label: str,
    raw_name: str,
    target_date: date,
    collector: Callable[..., list[dict]],
    max_results: int | None,
) -> None:
    """安全运行单个采集器。"""
    try:
        count = len(collector(target_date=target_date, max_results=max_results))
    except Exception as error:
        print(f"警告：{label}采集失败，已跳过该来源：{error}")
        _write_empty_raw(target_date, raw_name)
        _save_collect_error(target_date, label, error)
        return
    print(f"{label}采集完成：{count} 条")


def _run_collectors(target_date: date, max_papers: int | None, max_repos: int | None, max_news: int | None) -> None:
    """依次运行三个采集器，保证单个来源失败时仍能生成日报。"""
    error_file = RAW_DIR / f"errors_{target_date.isoformat()}.json"
    if error_file.exists():
        error_file.unlink()
    print("开始采集论文数据...")
    _safe_collect("论文数据", "papers", target_date, collect_papers, max_papers)
    print("开始采集 GitHub 项目...")
    _safe_collect("GitHub 项目", "github", target_date, collect_github, max_repos)
    print("开始采集行业动态...")
    _safe_collect("行业动态", "news", target_date, collect_news, max_news)


def render_markdown(summary: DailySummary) -> str:
    """把结构化摘要渲染为 Markdown。"""
    return Template(REPORT_TEMPLATE, trim_blocks=True, lstrip_blocks=True).render(summary=summary)


def write_report(summary: DailySummary) -> Path:
    """写入 reports/YYYY-MM-DD.md。"""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    output = REPORT_DIR / f"{summary.date}.md"
    output.write_text(render_markdown(summary), encoding="utf-8")
    return output


def _maybe_show_git_hint() -> None:
    """在非 Git 仓库中运行时给出轻量提示。"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return
    if result.returncode != 0:
        print("提示：当前目录还不是 Git 仓库，推送到 GitHub 前需要先执行 git init。")


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="一键生成具身智能中文 Markdown 日报")
    parser.add_argument("--date", type=str, default=date.today().isoformat(), help="日报日期")
    parser.add_argument("--skip-collect", action="store_true", help="跳过采集，直接使用 data/raw 中已有数据")
    parser.add_argument("--max-papers", type=int, default=None, help="最大论文数量")
    parser.add_argument("--max-repos", type=int, default=None, help="最大 GitHub 项目数量")
    parser.add_argument("--max-news", type=int, default=None, help="最大行业动态数量")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date)
    if not args.skip_collect:
        _run_collectors(target_date, args.max_papers, args.max_repos, args.max_news)

    print("开始生成中文摘要...")
    summary = summarize(target_date)
    output = write_report(summary)
    print(f"日报已生成：{output.relative_to(ROOT)}")
    _maybe_show_git_hint()


if __name__ == "__main__":
    sys.exit(main())

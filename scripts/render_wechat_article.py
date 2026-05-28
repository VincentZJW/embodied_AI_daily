from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"
PROCESSED_DIR = ROOT / "data" / "processed"
EXPORT_DIR = ROOT / "miniprogram_export"
ARTICLE_DIR = EXPORT_DIR / "articles"
MINIPROGRAM_DATA_DIR = ROOT / "miniprogram" / "data"

THEME = "tech-dark"
ACCENT_COLOR = "#4F8CFF"

ESSENTIAL_GLOSSARY = [
    {
        "term": "VLA",
        "explanation": "Vision-Language-Action，视觉-语言-动作模型，把视觉感知、语言指令和机器人动作统一到一个策略中。",
    },
    {
        "term": "Sim2Real",
        "explanation": "仿真到真实迁移，先在仿真环境训练或验证机器人策略，再迁移到真实机器人执行。",
    },
    {
        "term": "Diffusion Policy",
        "explanation": "扩散策略，用扩散模型生成连续动作序列，常用于机器人操作和轨迹规划任务。",
    },
    {
        "term": "Robot Foundation Model",
        "explanation": "机器人基础模型，面向多任务、多机器人和多场景泛化的通用机器人模型。",
    },
]

TAG_RULES = [
    ("VLA", ["VLA", "Vision-Language-Action", "QVLA", "SmolVLA", "π_0"]),
    ("Sim2Real", ["Sim2Real", "sim-to-real", "零样本实机", "仿真到真实"]),
    ("Diffusion Policy", ["Diffusion Policy", "扩散策略", "扩散动作"]),
    ("机器人基础模型", ["Robot Foundation Model", "基础模型", "foundation model"]),
    ("人形机器人", ["人形机器人", "humanoid", "Humanoid", "双足"]),
    ("世界模型", ["世界模型", "world model", "World"]),
    ("动作原语", ["动作原语", "motion primitive", "Primitive"]),
    ("量化部署", ["量化", "4bit", "W4A4", "端侧部署"]),
    ("机器人视觉", ["视觉", "相机", "GMSL", "传感器", "感知"]),
    ("触觉感知", ["触觉", "tactile", "uSkin"]),
    ("运动控制", ["运动控制", "冲刺", "控制系统", "motion control"]),
]


def _relative(path: Path) -> str:
    """生成适合命令行显示的相对路径。"""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _normalize_day(value: str) -> str:
    """校验并规范化日期字符串。"""
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise ValueError(f"错误：日期格式无效：{value}，请使用 YYYY-MM-DD。") from error


def _resolve_report_path(report_arg: str | None, date_arg: str | None) -> tuple[str, Path]:
    """根据命令行参数确定输入日报路径。"""
    if report_arg:
        report_path = Path(report_arg)
        if not report_path.is_absolute():
            report_path = ROOT / report_path
        day = _normalize_day(report_path.stem)
        return day, report_path

    day = _normalize_day(date_arg or date.today().isoformat())
    return day, REPORT_DIR / f"{day}.md"


def _require_report(day: str, report_path: Path, explicit_report: bool) -> None:
    """检查日报文件是否存在，并输出中文错误信息。"""
    if report_path.exists():
        return

    if not explicit_report and day == date.today().isoformat():
        raise FileNotFoundError(
            f"错误：今天的报告不存在：{_relative(report_path)}。请先运行 python scripts/render_report.py 生成 Markdown 日报。"
        )
    raise FileNotFoundError(
        f"错误：报告不存在：{_relative(report_path)}。请先生成对应日期的 Markdown 日报后再导出小程序文章数据。"
    )


def _load_processed_summary(day: str) -> dict[str, Any] | None:
    """优先读取摘要阶段生成的结构化中文数据。"""
    path = PROCESSED_DIR / f"summary_{day}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _section(markdown: str, heading: str) -> str:
    """提取指定二级标题下的正文。"""
    pattern = rf"^## {re.escape(heading)}\s*\n(?P<body>.*?)(?=^## |\Z)"
    match = re.search(pattern, markdown, flags=re.MULTILINE | re.DOTALL)
    return match.group("body").strip() if match else ""


def _bullet_items(block: str) -> list[str]:
    """提取 Markdown 无序列表内容。"""
    items: list[str] = []
    for line in block.splitlines():
        value = line.strip()
        if value.startswith("- "):
            items.append(value[2:].strip())
    return items


def _parse_titled_blocks(block: str) -> list[tuple[str, list[str]]]:
    """解析以三级标题分组的 Markdown 内容。"""
    items: list[tuple[str, list[str]]] = []
    current_title = ""
    current_lines: list[str] = []
    for line in block.splitlines():
        value = line.strip()
        if value.startswith("### "):
            if current_title:
                items.append((current_title, current_lines))
            current_title = value[4:].strip()
            current_lines = []
        elif current_title:
            current_lines.append(value)
    if current_title:
        items.append((current_title, current_lines))
    return items


def _after_prefix(value: str, prefix: str) -> str:
    """提取指定中文前缀后的内容。"""
    return value[len(prefix) :].strip() if value.startswith(prefix) else ""


def _parse_markdown_summary(day: str, markdown: str) -> dict[str, Any]:
    """在缺少结构化摘要时，从 Markdown 日报降级解析。"""
    papers: list[dict[str, Any]] = []
    for title, lines in _parse_titled_blocks(_section(markdown, "重点论文")):
        bullets = _bullet_items("\n".join(lines))
        papers.append(
            {
                "title_zh": title,
                "reason": next((_after_prefix(item, "关注原因：") for item in bullets if item.startswith("关注原因：")), ""),
                "highlights": [_after_prefix(item, "要点：") for item in bullets if item.startswith("要点：")],
                "url": next((_after_prefix(item, "来源：") for item in bullets if item.startswith("来源：")), ""),
            }
        )

    github_projects: list[dict[str, Any]] = []
    for name, lines in _parse_titled_blocks(_section(markdown, "重点 GitHub 项目")):
        bullets = _bullet_items("\n".join(lines))
        github_projects.append(
            {
                "name": name,
                "summary": next((_after_prefix(item, "中文摘要：") for item in bullets if item.startswith("中文摘要：")), ""),
                "why_follow": next((_after_prefix(item, "跟踪价值：") for item in bullets if item.startswith("跟踪价值：")), ""),
                "url": next((_after_prefix(item, "来源：") for item in bullets if item.startswith("来源：")), ""),
            }
        )

    news: list[dict[str, Any]] = []
    for title, lines in _parse_titled_blocks(_section(markdown, "行业/公司动态")):
        bullets = _bullet_items("\n".join(lines))
        news.append(
            {
                "title_zh": title,
                "summary": next((_after_prefix(item, "中文摘要：") for item in bullets if item.startswith("中文摘要：")), ""),
                "impact": next((_after_prefix(item, "影响判断：") for item in bullets if item.startswith("影响判断：")), ""),
                "url": next((_after_prefix(item, "来源：") for item in bullets if item.startswith("来源：")), ""),
            }
        )

    terms: list[dict[str, str]] = []
    for item in _bullet_items(_section(markdown, "技术词汇解释")):
        match = re.match(r"\*\*(?P<term>.+?)\*\*：(?P<explanation>.+)", item)
        if match:
            terms.append({"term": match.group("term").strip(), "explanation": match.group("explanation").strip()})

    sources: list[dict[str, str]] = []
    for item in _bullet_items(_section(markdown, "来源链接")):
        match = re.match(r"\[(?P<type>.+?)\]\s*(?P<name>.+?)：(?P<url>.+)", item)
        if match:
            sources.append(
                {
                    "type": match.group("type").strip(),
                    "name": match.group("name").strip(),
                    "url": match.group("url").strip(),
                }
            )

    return {
        "date": day,
        "core_conclusions": _bullet_items(_section(markdown, "今日核心结论")),
        "papers": papers,
        "github_projects": github_projects,
        "news": news,
        "terms": terms,
        "recruiting_insights": _bullet_items(_section(markdown, "对猎头/招聘的启发")),
        "sources": sources,
    }


def _text_for_tags(*values: Any) -> str:
    """合并文本，供标签和重要性计算使用。"""
    parts: list[str] = []
    for value in values:
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif value:
            parts.append(str(value))
    return " ".join(parts)


def _extract_tags(text: str, limit: int = 6) -> list[str]:
    """根据内容生成适合小程序展示的科技标签。"""
    tags = ["具身智能"]
    for tag, keywords in TAG_RULES:
        if any(keyword in text for keyword in keywords) and tag not in tags:
            tags.append(tag)
    if "机器人" in text and "机器人" not in tags:
        tags.append("机器人")
    return tags[:limit]


def _importance_score(text: str, index: int, base: int) -> int:
    """生成稳定的重要性分值，方便小程序排序或强调卡片。"""
    score = base - index * 3
    keyword_bonus = {
        "VLA": 5,
        "Robot Foundation Model": 5,
        "基础模型": 5,
        "Sim2Real": 4,
        "sim-to-real": 4,
        "人形机器人": 4,
        "真实": 3,
        "部署": 3,
        "量化": 3,
        "安全": 3,
    }
    for keyword, bonus in keyword_bonus.items():
        if keyword in text:
            score += bonus
    return max(60, min(score, 100))


def _glossary_key(term: str) -> str:
    """归一化术语名称，避免同义术语重复。"""
    value = term.lower().replace("-", "").replace("_", "").replace(" ", "")
    if value in {"sim2real", "simtoreal"}:
        return "sim2real"
    if value in {"visionlanguageaction", "vla"}:
        return "vla"
    return value


def _merge_glossary(terms: list[dict[str, Any]]) -> list[dict[str, str]]:
    """补齐关键术语的中文解释。"""
    merged: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in terms:
        term = str(item.get("term", "")).strip()
        explanation = str(item.get("explanation", "")).strip()
        if not term or not explanation:
            continue
        key = _glossary_key(term)
        if key in seen:
            continue
        merged.append({"term": term, "explanation": explanation})
        seen.add(key)

    for item in ESSENTIAL_GLOSSARY:
        key = _glossary_key(item["term"])
        if key not in seen:
            merged.append(item)
            seen.add(key)

    return merged


def _subtitle(summary: dict[str, Any]) -> str:
    """生成中文副标题。"""
    text = _text_for_tags(
        summary.get("core_conclusions", []),
        [item.get("title_zh", "") for item in summary.get("papers", [])],
        [item.get("summary", "") for item in summary.get("github_projects", [])],
        [item.get("title_zh", "") for item in summary.get("news", [])],
    )
    tags = [tag for tag in _extract_tags(text, limit=5) if tag != "具身智能"]
    if tags:
        return f"聚焦{'、'.join(tags[:3])}，追踪论文、开源项目与产业动态。"
    return "追踪具身智能论文、开源项目与产业动态。"


def _summary_cards(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """生成核心结论卡片。"""
    cards: list[dict[str, Any]] = []
    for index, item in enumerate(summary.get("core_conclusions", [])):
        text = str(item).strip()
        if not text:
            continue
        cards.append(
            {
                "title": f"核心结论 {index + 1}",
                "content": text,
                "card_type": "核心摘要卡",
                "importance_score": _importance_score(text, index, 96),
                "tags": _extract_tags(text),
            }
        )
    return cards


def _paper_cards(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """生成论文卡片。"""
    cards: list[dict[str, Any]] = []
    for index, item in enumerate(summary.get("papers", [])):
        text = _text_for_tags(item.get("title_zh"), item.get("reason"), item.get("highlights", []))
        cards.append(
            {
                "title": item.get("title_zh", ""),
                "reason": item.get("reason", ""),
                "highlights": item.get("highlights", []),
                "source_url": item.get("url", ""),
                "card_type": "重点论文卡",
                "importance_score": _importance_score(text, index, 94),
                "tags": _extract_tags(text),
            }
        )
    return cards


def _github_cards(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """生成 GitHub 项目卡片。"""
    cards: list[dict[str, Any]] = []
    for index, item in enumerate(summary.get("github_projects", [])):
        text = _text_for_tags(item.get("name"), item.get("summary"), item.get("why_follow"))
        cards.append(
            {
                "name": item.get("name", ""),
                "summary": item.get("summary", ""),
                "why_follow": item.get("why_follow", ""),
                "source_url": item.get("url", ""),
                "card_type": "开源项目卡",
                "importance_score": _importance_score(text, index, 90),
                "tags": _extract_tags(text),
            }
        )
    return cards


def _industry_cards(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """生成行业动态卡片。"""
    cards: list[dict[str, Any]] = []
    for index, item in enumerate(summary.get("news", [])):
        text = _text_for_tags(item.get("title_zh"), item.get("summary"), item.get("impact"))
        cards.append(
            {
                "title": item.get("title_zh", ""),
                "summary": item.get("summary", ""),
                "impact": item.get("impact", ""),
                "source_url": item.get("url", ""),
                "card_type": "行业动态卡",
                "importance_score": _importance_score(text, index, 86),
                "tags": _extract_tags(text),
            }
        )
    return cards


def _glossary_cards(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """生成术语解释卡片。"""
    cards: list[dict[str, Any]] = []
    for index, item in enumerate(_merge_glossary(summary.get("terms", []))):
        text = _text_for_tags(item.get("term"), item.get("explanation"))
        cards.append(
            {
                "term": item.get("term", ""),
                "explanation": item.get("explanation", ""),
                "card_type": "术语解释卡",
                "importance_score": _importance_score(text, index, 88),
                "tags": _extract_tags(text),
            }
        )
    return cards


def _recruiting_cards(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """生成招聘洞察卡片。"""
    cards: list[dict[str, Any]] = []
    for index, item in enumerate(summary.get("recruiting_insights", [])):
        text = str(item).strip()
        if not text:
            continue
        cards.append(
            {
                "content": text,
                "card_type": "招聘洞察卡",
                "importance_score": _importance_score(text, index, 84),
                "tags": _extract_tags(text),
            }
        )
    return cards


def _source_cards(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """生成来源链接卡片。"""
    cards: list[dict[str, Any]] = []
    source_names: dict[str, str] = {}
    for item in summary.get("papers", []):
        if item.get("url") and item.get("title_zh"):
            source_names[item["url"]] = item["title_zh"]
    for item in summary.get("github_projects", []):
        if item.get("url") and item.get("name"):
            source_names[item["url"]] = item["name"]
    for item in summary.get("news", []):
        if item.get("url") and item.get("title_zh"):
            source_names[item["url"]] = item["title_zh"]

    for index, item in enumerate(summary.get("sources", [])):
        source_type = item.get("type", "")
        source_url = item.get("url", "")
        source_name = source_names.get(source_url, item.get("name", ""))
        text = _text_for_tags(source_type, source_name, source_url)
        cards.append(
            {
                "name": source_name,
                "url": source_url,
                "type": source_type,
                "card_type": "来源链接卡",
                "importance_score": _importance_score(text, index, 78),
            }
        )
    return cards


def build_wechat_article(day: str, summary: dict[str, Any]) -> dict[str, Any]:
    """把日报摘要转换为微信小程序可读取的文章 JSON。"""
    all_text = _text_for_tags(
        summary.get("core_conclusions", []),
        [item.get("title_zh", "") for item in summary.get("papers", [])],
        [item.get("summary", "") for item in summary.get("github_projects", [])],
        [item.get("title_zh", "") for item in summary.get("news", [])],
        [item.get("term", "") for item in summary.get("terms", [])],
    )
    return {
        "title": f"具身智能中文日报｜{day}",
        "date": day,
        "subtitle": _subtitle(summary),
        "theme": THEME,
        "accent_color": ACCENT_COLOR,
        "tags": _extract_tags(all_text, limit=8),
        "export_note": "未发布到微信平台，仅生成小程序可读取的数据文件。",
        "executive_summary": _summary_cards(summary),
        "papers": _paper_cards(summary),
        "github_projects": _github_cards(summary),
        "industry_updates": _industry_cards(summary),
        "glossary": _glossary_cards(summary),
        "recruiting_insights": _recruiting_cards(summary),
        "sources": _source_cards(summary),
    }


def _write_miniprogram_data_module(payload: str) -> None:
    """同步生成小程序前端可直接引用的数据模块。"""
    MINIPROGRAM_DATA_DIR.mkdir(parents=True, exist_ok=True)
    module_path = MINIPROGRAM_DATA_DIR / "latest.js"
    module_path.write_text(f"const latestArticle = {payload};\n\nmodule.exports = latestArticle;\n", encoding="utf-8")


def export_wechat_article(target_date: date | str | None = None, report_path: Path | None = None) -> Path:
    """导出指定日期的微信小程序文章数据，并同步 latest.json。"""
    if report_path:
        day = _normalize_day(report_path.stem)
        resolved_report_path = report_path
        if not resolved_report_path.is_absolute():
            resolved_report_path = ROOT / resolved_report_path
    else:
        if isinstance(target_date, date):
            day = target_date.isoformat()
        elif isinstance(target_date, str):
            day = _normalize_day(target_date)
        else:
            day = date.today().isoformat()
        resolved_report_path = REPORT_DIR / f"{day}.md"

    _require_report(day, resolved_report_path, explicit_report=report_path is not None)
    markdown = resolved_report_path.read_text(encoding="utf-8")
    summary = _load_processed_summary(day) or _parse_markdown_summary(day, markdown)
    article = build_wechat_article(day, summary)

    ARTICLE_DIR.mkdir(parents=True, exist_ok=True)
    article_path = ARTICLE_DIR / f"{day}.json"
    latest_path = EXPORT_DIR / "latest.json"
    payload = json.dumps(article, ensure_ascii=False, indent=2)
    article_path.write_text(payload + "\n", encoding="utf-8")
    latest_path.write_text(payload + "\n", encoding="utf-8")
    _write_miniprogram_data_module(payload)
    return article_path


def main() -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="导出微信小程序科技风文章 JSON")
    parser.add_argument("report", nargs="?", help="Markdown 日报路径，默认读取 reports/今天日期.md")
    parser.add_argument("--date", type=str, default=None, help="日报日期，格式为 YYYY-MM-DD")
    args = parser.parse_args()

    try:
        day, report_path = _resolve_report_path(args.report, args.date)
        _require_report(day, report_path, explicit_report=args.report is not None)
        output = export_wechat_article(day, report_path=report_path)
    except json.JSONDecodeError:
        print("错误：JSON 文件解析失败，请检查结构化摘要文件或重新生成日报。", file=sys.stderr)
        return 1
    except (FileNotFoundError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1

    print(f"微信小程序文章数据已生成：{_relative(output)}")
    print(f"最新文章索引已更新：{_relative(EXPORT_DIR / 'latest.json')}")
    print(f"小程序前端数据已同步：{_relative(MINIPROGRAM_DATA_DIR / 'latest.js')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

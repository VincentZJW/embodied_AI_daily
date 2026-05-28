from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError
from pydantic import BaseModel, Field
from rapidfuzz import fuzz


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"


class PaperSummary(BaseModel):
    title_zh: str
    reason: str
    highlights: list[str] = Field(default_factory=list)
    url: str


class GitHubSummary(BaseModel):
    name: str
    summary: str
    why_follow: str
    url: str


class NewsSummary(BaseModel):
    title_zh: str
    summary: str
    impact: str
    url: str


class TermSummary(BaseModel):
    term: str
    explanation: str


class SourceSummary(BaseModel):
    name: str
    url: str
    type: str


class DailySummary(BaseModel):
    date: str
    core_conclusions: list[str] = Field(default_factory=list)
    papers: list[PaperSummary] = Field(default_factory=list)
    github_projects: list[GitHubSummary] = Field(default_factory=list)
    news: list[NewsSummary] = Field(default_factory=list)
    terms: list[TermSummary] = Field(default_factory=list)
    recruiting_insights: list[str] = Field(default_factory=list)
    sources: list[SourceSummary] = Field(default_factory=list)


TERM_HINTS = {
    "VLA": "Vision-Language-Action，视觉-语言-动作模型，把视觉感知、语言指令和机器人动作统一建模。",
    "Sim2Real": "仿真到真实迁移，先在仿真环境训练策略，再迁移到真实机器人执行。",
    "Diffusion Policy": "扩散策略，用扩散模型生成连续动作轨迹，常用于机器人操作任务。",
    "Robot Foundation Model": "机器人基础模型，面向多机器人、多任务和多场景泛化的通用模型。",
    "Humanoid Robot": "人形机器人，形态接近人类，适合研究双足移动、全身控制和通用操作。",
}


def _read_json(path: Path) -> list[dict[str, Any]]:
    """读取采集脚本写出的 JSON 数组。"""
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def load_raw_data(target_date: date) -> dict[str, list[dict[str, Any]]]:
    """按日期加载原始数据。"""
    day = target_date.isoformat()
    return {
        "papers": _read_json(RAW_DIR / f"papers_{day}.json"),
        "github": _read_json(RAW_DIR / f"github_{day}.json"),
        "news": _read_json(RAW_DIR / f"news_{day}.json"),
        "errors": _read_json(RAW_DIR / f"errors_{day}.json"),
    }


def _limit_text(value: str, max_chars: int = 900) -> str:
    """限制传给模型的单条文本长度。"""
    value = " ".join((value or "").split())
    return value[:max_chars]


def _compact_payload(raw_data: dict[str, list[dict[str, Any]]], max_items: int) -> dict[str, Any]:
    """压缩原始数据，降低摘要成本。"""
    papers = [
        {
            "title": item.get("title", ""),
            "abstract": _limit_text(item.get("abstract", "")),
            "authors": item.get("authors", [])[:8],
            "published": item.get("published"),
            "url": item.get("url") or item.get("pdf_url"),
            "categories": item.get("categories", []),
        }
        for item in raw_data.get("papers", [])[:max_items]
    ]
    github = [
        {
            "name": item.get("full_name") or item.get("name"),
            "description": _limit_text(item.get("description", ""), 500),
            "readme": _limit_text(item.get("readme_text", ""), 1200),
            "readme_url": item.get("readme_url"),
            "stars": item.get("stars", 0),
            "language": item.get("language"),
            "topics": item.get("topics", [])[:10],
            "url": item.get("html_url"),
        }
        for item in raw_data.get("github", [])[:max_items]
    ]
    news = [
        {
            "title": item.get("title", ""),
            "summary": _limit_text(item.get("summary", ""), 700),
            "published": item.get("published"),
            "url": item.get("url"),
            "feed_url": item.get("feed_url"),
        }
        for item in raw_data.get("news", [])[:max_items]
    ]
    return {
        "papers": papers,
        "github": github,
        "news": news,
        "errors": raw_data.get("errors", []),
    }


def _openai_summary(target_date: date, raw_data: dict[str, list[dict[str, Any]]]) -> DailySummary:
    """调用 OpenAI，把英文资料理解后生成中文结构化摘要。"""
    model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
    max_items = int(os.getenv("SUMMARY_MAX_ITEMS", "6"))
    payload = _compact_payload(raw_data, max_items=max_items)

    system_prompt = (
        "你是具身智能中文日报编辑。你必须严格基于输入资料写作，不编造不存在的结果。"
        "如果资料是英文，先理解内容，再用中文总结。必要英文术语可以保留，但要配中文解释。"
        "输出必须是合法 JSON，不要输出 Markdown，不要添加 JSON 之外的文字。"
    )
    user_prompt = {
        "任务": "生成具身智能中文日报结构化摘要",
        "日期": target_date.isoformat(),
        "输出格式": {
            "date": "YYYY-MM-DD",
            "core_conclusions": ["中文核心结论"],
            "papers": [
                {
                    "title_zh": "中文论文标题或中文主题概括",
                    "reason": "为什么值得关注",
                    "highlights": ["中文要点"],
                    "url": "来源链接",
                }
            ],
            "github_projects": [
                {
                    "name": "仓库名",
                    "summary": "中文项目摘要",
                    "why_follow": "为什么值得跟踪",
                    "url": "来源链接",
                }
            ],
            "news": [
                {
                    "title_zh": "中文动态标题",
                    "summary": "中文摘要",
                    "impact": "对具身智能产业或研发的影响",
                    "url": "来源链接",
                }
            ],
            "terms": [{"term": "术语", "explanation": "中文解释"}],
            "recruiting_insights": ["对猎头和招聘的启发"],
            "sources": [{"name": "来源名称", "url": "链接", "type": "论文/GitHub/行业动态"}],
        },
        "输入资料": payload,
    }

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)},
        ],
    )
    content = response.choices[0].message.content or "{}"
    data = json.loads(content)
    data["date"] = target_date.isoformat()
    return DailySummary.model_validate(data)


def _guess_topic(text: str) -> str:
    """在没有大模型时，用关键词给出中文主题概括。"""
    lowered = text.lower()
    candidates = [
        ("视觉-语言-动作模型", ["vision-language-action", "vla", "language action"]),
        ("扩散策略机器人控制", ["diffusion policy", "diffusion"]),
        ("仿真到真实迁移", ["sim2real", "simulation", "sim-to-real"]),
        ("人形机器人控制", ["humanoid", "biped"]),
        ("机器人操作与抓取", ["manipulation", "grasp", "dexterous"]),
        ("机器人基础模型", ["foundation model", "generalist", "general-purpose"]),
        ("具身智能评测与数据集", ["benchmark", "dataset", "evaluation"]),
    ]
    best_topic = "具身智能研发"
    best_score = 0
    for topic, words in candidates:
        score = max(fuzz.partial_ratio(word, lowered) for word in words)
        if score > best_score:
            best_topic = topic
            best_score = score
    return best_topic


def _fallback_summary(target_date: date, raw_data: dict[str, list[dict[str, Any]]]) -> DailySummary:
    """没有 OpenAI API Key 时生成低保真中文日报骨架。"""
    papers: list[PaperSummary] = []
    for index, item in enumerate(raw_data.get("papers", [])[:5], start=1):
        topic = _guess_topic(f"{item.get('title', '')} {item.get('abstract', '')}")
        papers.append(
            PaperSummary(
                title_zh=f"论文 {index}：{topic}",
                reason=f"该论文与{topic}相关，建议配置 OpenAI API Key 后生成更准确的中文精读摘要。",
                highlights=[
                    "已从 arXiv API 合规获取元数据。",
                    "当前为规则摘要，未进行深度语义翻译。",
                ],
                url=item.get("url") or item.get("pdf_url") or "",
            )
        )

    projects: list[GitHubSummary] = []
    for item in raw_data.get("github", [])[:5]:
        topic = _guess_topic(f"{item.get('name', '')} {item.get('description', '')}")
        projects.append(
            GitHubSummary(
                name=item.get("full_name") or item.get("name") or "未命名项目",
                summary=f"该项目可能聚焦{topic}，主要语言为 {item.get('language') or '未知'}。",
                why_follow=f"仓库星标数约为 {item.get('stars', 0)}，可用于观察开源社区对{topic}的实现方向。",
                url=item.get("html_url") or "",
            )
        )

    news_items: list[NewsSummary] = []
    for index, item in enumerate(raw_data.get("news", [])[:5], start=1):
        topic = _guess_topic(f"{item.get('title', '')} {item.get('summary', '')}")
        news_items.append(
            NewsSummary(
                title_zh=f"行业动态 {index}：{topic}",
                summary=f"该动态与{topic}相关，建议配置 OpenAI API Key 后生成更准确的中文摘要。",
                impact="可作为跟踪产业落地、公司研发投入和招聘需求变化的线索。",
                url=item.get("url") or "",
            )
        )

    term_names = ["VLA", "Sim2Real", "Diffusion Policy", "Robot Foundation Model", "Humanoid Robot"]
    terms = [TermSummary(term=name, explanation=TERM_HINTS[name]) for name in term_names]

    sources: list[SourceSummary] = []
    for index, item in enumerate(raw_data.get("papers", [])[:5], start=1):
        sources.append(SourceSummary(name=f"arXiv 论文 {index}", url=item.get("url") or "", type="论文"))
    for item in raw_data.get("github", [])[:5]:
        sources.append(
            SourceSummary(
                name=item.get("full_name") or item.get("name") or "GitHub 项目",
                url=item.get("html_url") or "",
                type="GitHub",
            )
        )
    for index, item in enumerate(raw_data.get("news", [])[:5], start=1):
        sources.append(SourceSummary(name=f"RSS 动态 {index}", url=item.get("url") or "", type="行业动态"))

    counts_line = (
        f"本次采集得到论文 {len(raw_data.get('papers', []))} 篇、"
        f"GitHub 项目 {len(raw_data.get('github', []))} 个、"
        f"行业/公司动态 {len(raw_data.get('news', []))} 条。"
    )
    error_items = raw_data.get("errors", [])
    if error_items:
        error_line = "部分来源采集失败：" + "；".join(
            f"{item.get('source', '未知来源')}：{item.get('error', '未知错误')}" for item in error_items
        )
    else:
        error_line = "本次运行未记录采集错误。"

    return DailySummary(
        date=target_date.isoformat(),
        core_conclusions=[
            counts_line,
            error_line,
            "当前未配置 OpenAI API Key，因此摘要为规则生成版本；配置后可生成更准确的中文理解和翻译。",
            "从招聘视角看，VLA、机器人操作、Sim2Real 和人形机器人仍是值得持续追踪的方向。",
        ],
        papers=papers,
        github_projects=projects,
        news=news_items,
        terms=terms,
        recruiting_insights=[
            "关注同时理解机器人控制、视觉语言模型和真实硬件部署的人才。",
            "候选人如果具备开源项目复现、数据集构建和 Sim2Real 经验，匹配度通常更高。",
            "人形机器人岗位可重点筛选全身控制、强化学习、运动规划和嵌入式部署背景。",
        ],
        sources=sources,
    )


def summarize(target_date: date | None = None) -> DailySummary:
    """生成并保存结构化中文摘要。"""
    load_dotenv(ROOT / ".env")
    target_date = target_date or date.today()
    raw_data = load_raw_data(target_date)

    if os.getenv("OPENAI_API_KEY"):
        try:
            summary = _openai_summary(target_date, raw_data)
        except OpenAIError as exc:
            summary = _fallback_summary(target_date, raw_data)
            summary.core_conclusions.insert(
                0,
                f"OpenAI API 调用失败：{exc}。已自动改用规则摘要，建议检查 OPENAI_API_KEY、OPENAI_MODEL 和网络配置。",
            )
        except (json.JSONDecodeError, ValueError) as exc:
            summary = _fallback_summary(target_date, raw_data)
            summary.core_conclusions.insert(
                0,
                f"OpenAI 返回内容解析失败：{exc}。已自动改用规则摘要，建议检查模型输出是否为合法 JSON。",
            )
    else:
        summary = _fallback_summary(target_date, raw_data)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    output = PROCESSED_DIR / f"summary_{target_date.isoformat()}.json"
    output.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    return summary


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="生成具身智能中文日报结构化摘要")
    parser.add_argument("--date", type=str, default=date.today().isoformat(), help="日报日期")
    args = parser.parse_args()

    summary = summarize(date.fromisoformat(args.date))
    print(f"已生成结构化摘要：{summary.date}")


if __name__ == "__main__":
    main()

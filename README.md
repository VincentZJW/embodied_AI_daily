# 具身智能中文日报自动化系统

这是一个最小可行版本 MVP，用于每天自动采集和整理具身智能相关论文、GitHub 项目、行业/公司动态，并生成中文 Markdown 日报。

系统不会爬取 Google Scholar 搜索页。当前优先使用 arXiv API、GitHub REST API、RSS feeds；后续可以继续扩展 Semantic Scholar API、Crossref API 和公司官网博客。

## 功能

- 自动采集近期具身智能论文，保存到 `data/raw/papers_YYYY-MM-DD.json`
- 自动搜索近期活跃 GitHub 项目，保存到 `data/raw/github_YYYY-MM-DD.json`
- 自动拉取入选 GitHub 项目的 README 片段，用于中文理解和总结
- 自动读取机器人和 AI 相关 RSS 动态，保存到 `data/raw/news_YYYY-MM-DD.json`
- 使用 OpenAI API 把英文资料理解后生成中文结构化摘要
- 渲染 `reports/YYYY-MM-DD.md`
- GitHub Actions 每天自动运行，并把新日报 commit 回仓库

## 日报结构

每份日报包含：

- 今日核心结论
- 重点论文
- 重点 GitHub 项目
- 行业/公司动态
- 技术词汇解释
- 对猎头/招聘的启发
- 来源链接

## 本地运行

需要 Python 3.12。

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

编辑 `.env`，至少建议配置：

```bash
OPENAI_API_KEY=你的 OpenAI API Key
OPENAI_MODEL=gpt-5.4-mini
GITHUB_TOKEN=你的 GitHub Token
```

生成今天的日报：

```bash
python scripts/render_report.py
```

生成指定日期的日报：

```bash
python scripts/render_report.py --date 2026-05-28
```

如果已经有 `data/raw/` 原始数据，只想重新生成摘要和 Markdown：

```bash
python scripts/render_report.py --skip-collect
```

生成结果位于：

```text
reports/YYYY-MM-DD.md
```

## API Key 配置

### OpenAI

`OPENAI_API_KEY` 用于把英文论文摘要、GitHub README 描述、新闻条目理解后转写为中文日报内容。没有配置时，系统仍会生成日报骨架，但摘要质量较低，不适合作为正式日报。

本地配置方式：

```bash
OPENAI_API_KEY=你的 OpenAI API Key
OPENAI_MODEL=gpt-5.4-mini
```

默认推荐使用 `gpt-5.4-mini`。该日报系统主要用于论文、GitHub 项目和行业动态的中文总结，通常不需要每天使用更高成本模型；如需更强推理或更长上下文能力，可以在 `.env` 或 GitHub Actions Variables 中把 `OPENAI_MODEL` 改成其他兼容模型。

GitHub Actions 配置方式：

1. 进入 GitHub 仓库的 `Settings`
2. 打开 `Secrets and variables` -> `Actions`
3. 在 `Secrets` 中新增 `OPENAI_API_KEY`
4. 可选：在 `Variables` 中新增 `OPENAI_MODEL`

### GitHub

`GITHUB_TOKEN` 用于提高 GitHub Search API 的请求限额。

本地可以写入 `.env`：

```bash
GITHUB_TOKEN=你的 GitHub Token
```

在 GitHub Actions 中，默认的 `${{ secrets.GITHUB_TOKEN }}` 会自动提供给 workflow；如果需要更高权限或跨仓库访问，可自行配置同名 Secret。

### 自定义 RSS 源

可以用英文逗号追加 RSS 源：

```bash
NEWS_RSS_FEEDS=https://example.com/feed.xml,https://example.org/rss
```

## 推送到 GitHub

如果当前目录还不是 Git 仓库，先初始化：

```bash
git init
git add .
git commit -m "初始化具身智能中文日报自动化系统"
```

在 GitHub 创建一个空仓库后，绑定远程仓库并推送：

```bash
git remote add origin git@github.com:你的用户名/你的仓库名.git
git branch -M main
git push -u origin main
```

推送后，在 GitHub 仓库中配置 `OPENAI_API_KEY`，再进入 `Actions` 手动运行一次“生成具身智能中文日报”工作流，确认可以自动生成并提交 `reports/YYYY-MM-DD.md`。

## 项目结构

```text
scripts/collect_papers.py        # 从 arXiv API 采集论文
scripts/collect_github.py        # 从 GitHub REST API 采集项目
scripts/collect_news.py          # 从 RSS feeds 采集行业动态
scripts/summarize.py             # 生成中文结构化摘要
scripts/render_report.py         # 渲染 Markdown 日报
reports/                         # 每日 Markdown 报告
data/raw/                        # 原始采集数据
data/processed/                  # 结构化中文摘要
.github/workflows/daily.yml      # 每日自动运行工作流
.env.example                     # 环境变量示例
.codex/skills/embodied-ai-daily/ # Codex 技能说明
```

## MVP 边界

- 当前版本不直接抓取网页全文，只使用 API 和 RSS 中的结构化字段。
- 当前版本不爬取 Google Scholar。
- GitHub README 当前只拉取前几千字符，后续可以增加完整 README 分段摘要。
- Semantic Scholar API 和 Crossref API 已预留为后续扩展方向，MVP 先以 arXiv API 为主。

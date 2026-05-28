# 具身智能中文日报自动化技能

## 适用场景

当用户希望创建、运行、维护或扩展“具身智能中文日报自动化系统”时使用本技能。系统目标是每天自动搜索和整理具身智能相关论文、技术报告、GitHub 项目、行业动态，并生成中文 Markdown 日报。

## 核心原则

- 所有代码注释、README、日报正文和给用户看的说明都使用中文。
- 英文论文、报告、网页、GitHub README 需要先理解内容，再翻译或转写成中文总结。
- 必要英文术语可以保留，例如 VLA、Sim2Real、Diffusion Policy、Robot Foundation Model、Humanoid Robot，但必须配中文解释。
- 不直接爬取 Google Scholar 搜索页。
- 优先使用合规来源：arXiv API、Semantic Scholar API、Crossref API、GitHub REST API、RSS feeds、公司官网博客。
- MVP 优先保证可本地运行、结构清晰、可每日自动生成 `reports/YYYY-MM-DD.md`。

## 推荐工作流

1. 运行采集：

   ```bash
   python scripts/render_report.py
   ```

2. 只重新渲染已有数据：

   ```bash
   python scripts/render_report.py --skip-collect
   ```

3. 检查输出文件：

   ```text
   reports/YYYY-MM-DD.md
   data/raw/
   data/processed/
   ```

4. 如果摘要质量不足，优先检查 `.env` 中是否配置 `OPENAI_API_KEY`。

## 扩展建议

- 论文侧：在 `scripts/collect_papers.py` 中增加 Semantic Scholar API 和 Crossref API 补充引用数、作者机构、会议期刊信息。
- GitHub 侧：在 `scripts/collect_github.py` 中增加 README 拉取和最近 commit 活跃度分析。
- 新闻侧：在 `scripts/collect_news.py` 中增加公司官网博客 RSS 或公告页。
- 摘要侧：在 `scripts/summarize.py` 中保持 JSON 结构稳定，避免让渲染层依赖非结构化文本。
- 渲染侧：在 `scripts/render_report.py` 中保留固定栏目，确保日报对招聘和业务读者可读。

## 质量检查

- 运行 `python -m compileall scripts` 检查语法。
- 运行 `python scripts/render_report.py --skip-collect` 检查在无网络数据时能否生成日报骨架。
- 不要把 `.env` 提交到 Git。

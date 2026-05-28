const latestArticle = require("../../data/latest")

const DEFAULT_ARTICLE = {
  title: "具身智能中文日报",
  date: "",
  subtitle: "暂无日报数据",
  theme: "tech-dark",
  accent_color: "#4F8CFF",
  tags: ["具身智能"],
  executive_summary: [],
  papers: [],
  github_projects: [],
  industry_updates: [],
  glossary: [],
  recruiting_insights: [],
  sources: []
}

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function compactText(values) {
  return asArray(values).filter(Boolean).join(" ")
}

function scoreText(score) {
  return typeof score === "number" ? `重要度 ${score}` : ""
}

function buildCard(raw, sectionKey, index) {
  const card = {
    id: `${sectionKey}-${index}`,
    cardType: raw.card_type || "",
    title: "",
    subtitle: "",
    body: "",
    bullets: [],
    tags: asArray(raw.tags).slice(0, 5),
    scoreText: scoreText(raw.importance_score),
    url: raw.source_url || raw.url || ""
  }

  if (sectionKey === "executive_summary") {
    card.title = raw.title || `核心结论 ${index + 1}`
    card.body = raw.content || ""
  }

  if (sectionKey === "papers") {
    card.title = raw.title || `重点论文 ${index + 1}`
    card.subtitle = raw.reason || ""
    card.bullets = asArray(raw.highlights)
  }

  if (sectionKey === "github_projects") {
    card.title = raw.name || `开源项目 ${index + 1}`
    card.subtitle = raw.summary || ""
    card.body = raw.why_follow || ""
  }

  if (sectionKey === "industry_updates") {
    card.title = raw.title || `行业动态 ${index + 1}`
    card.subtitle = raw.summary || ""
    card.body = raw.impact || ""
  }

  if (sectionKey === "glossary") {
    card.title = raw.term || `技术术语 ${index + 1}`
    card.body = raw.explanation || ""
  }

  if (sectionKey === "recruiting_insights") {
    card.title = `招聘洞察 ${index + 1}`
    card.body = raw.content || ""
  }

  if (sectionKey === "sources") {
    card.title = raw.name || `来源 ${index + 1}`
    card.subtitle = raw.type || ""
    card.body = raw.url || ""
    card.url = raw.url || ""
  }

  return card
}

function buildSection(article, key, title, eyebrow) {
  const items = asArray(article[key]).map((item, index) => buildCard(item, key, index))
  return {
    key,
    title,
    eyebrow,
    countText: `${items.length} 条`,
    items
  }
}

function prepareArticle(article) {
  const safeArticle = Object.assign({}, DEFAULT_ARTICLE, article || {})
  const sections = [
    buildSection(safeArticle, "executive_summary", "今日核心摘要", "总览"),
    buildSection(safeArticle, "papers", "重点论文", "研究前沿"),
    buildSection(safeArticle, "github_projects", "开源项目", "工程线索"),
    buildSection(safeArticle, "industry_updates", "行业动态", "产业观察"),
    buildSection(safeArticle, "glossary", "技术词汇", "术语解释"),
    buildSection(safeArticle, "recruiting_insights", "招聘洞察", "人才信号"),
    buildSection(safeArticle, "sources", "来源链接", "资料索引")
  ].filter((section) => section.items.length > 0)

  return {
    article: safeArticle,
    sections,
    summaryText: compactText(asArray(safeArticle.executive_summary).map((item) => item.content)).slice(0, 96)
  }
}

Page({
  data: {
    article: DEFAULT_ARTICLE,
    sections: [],
    summaryText: ""
  },

  onLoad() {
    const prepared = prepareArticle(latestArticle)
    this.setData(prepared)
  },

  copySource(event) {
    const url = event.currentTarget.dataset.url
    if (!url) {
      return
    }
    wx.setClipboardData({
      data: url,
      success() {
        wx.showToast({
          title: "来源链接已复制",
          icon: "success"
        })
      }
    })
  }
})

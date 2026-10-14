export interface NoticeSection {
  title: string
  paragraphs: string[]
}

/** Split the notices file into its `## ` sections; the `# ` title and anything before it is dropped. */
export function parseNotices(raw: string): NoticeSection[] {
  const sections: NoticeSection[] = []
  for (const block of raw.split(/^## /m).slice(1)) {
    const [title = '', ...rest] = block.split('\n')
    const paragraphs = rest
      .join('\n')
      .split(/\n{2,}/)
      .map(p => p.trim())
      .filter(Boolean)
    sections.push({ title: title.trim(), paragraphs })
  }
  return sections
}

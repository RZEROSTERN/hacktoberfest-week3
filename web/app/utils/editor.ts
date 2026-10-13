import type { DraftItem, ProposalSection, SectionEdit } from '~/types/api'

/** Sections whose whole content is one block of text. */
const TEXT_ONLY = ['summary', 'problem', 'timeline', 'terms']
/** Sections that are lists of items with sources. */
const ITEM_SECTIONS = ['scope', 'deliverables', 'out_of_scope']

export const isTextOnly = (id: string) => TEXT_ONLY.includes(id)
export const isItemSection = (id: string) => ITEM_SECTIONS.includes(id)

export function cloneSections(sections: ProposalSection[]): ProposalSection[] {
  return structuredClone(JSON.parse(JSON.stringify(sections))) as ProposalSection[]
}

/** A new item written by the user: it has no source in the call, so it is an assumption. */
export function newItem(): DraftItem {
  return { text: '', assumption: true, sources: [] }
}

/** An item with no source is always an assumption, whoever wrote it. */
export function effectiveAssumption(item: DraftItem): boolean {
  return item.assumption || item.sources.length === 0
}

function itemsPayload(items: DraftItem[], flag: boolean) {
  return items
    .filter(i => i.text.trim())
    .map(i => ({
      text: i.text.trim(),
      assumption: flag ? effectiveAssumption(i) : false,
      segment_ids: i.sources.map(s => s.segment_id),
    }))
}

/** The edit request for the whole proposal, built from what the editor shows. */
export function toPayload(sections: ProposalSection[]): SectionEdit[] {
  return sections.map((s): SectionEdit => {
    if (isTextOnly(s.id)) return { id: s.id, text: s.text }
    if (isItemSection(s.id)) return { id: s.id, items: itemsPayload(s.items, true) }
    if (s.id === 'open_questions') return { id: s.id, lines: s.lines.filter(l => l.trim()) }
    // investment: the price sentence, the rate lines, and the client's budget note (removable only)
    return { id: s.id, text: s.text, lines: s.lines.filter(l => l.trim()), items: itemsPayload(s.items, false) }
  })
}

export function isDirty(original: ProposalSection[], edited: ProposalSection[]): boolean {
  return JSON.stringify(toPayload(original)) !== JSON.stringify(toPayload(edited))
}

/** `attachment; filename="propuesta-kevin.pdf"` -> `propuesta-kevin.pdf` */
export function filenameFromDisposition(header: string | null, fallback: string): string {
  const match = /filename="?([^";]+)"?/i.exec(header ?? '')
  return match?.[1] ?? fallback
}

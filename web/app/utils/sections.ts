/** The proposal sections in their default order, with the names shown in the profile form. */
export const SECTIONS: { id: string, label: string }[] = [
  { id: 'summary', label: 'Summary' },
  { id: 'problem', label: 'Understanding of the problem' },
  { id: 'scope', label: 'Scope' },
  { id: 'deliverables', label: 'Deliverables' },
  { id: 'out_of_scope', label: 'Out of scope' },
  { id: 'timeline', label: 'Timeline' },
  { id: 'open_questions', label: 'Open questions' },
  { id: 'investment', label: 'Investment' },
  { id: 'terms', label: 'Terms' },
]

export interface SectionChoice {
  id: string
  enabled: boolean
}

/** Pricing always comes after the scope: if it was placed before, move it right after. */
export function keepPricingAfterScope(choices: SectionChoice[]): SectionChoice[] {
  const result = [...choices]
  const investment = result.findIndex(c => c.id === 'investment')
  const scope = result.findIndex(c => c.id === 'scope')
  if (investment !== -1 && scope !== -1 && investment < scope) {
    const [moved] = result.splice(investment, 1)
    result.splice(result.findIndex(c => c.id === 'scope') + 1, 0, moved!)
  }
  return result
}

/** Rebuild the full list for the form from the saved preference (empty = all, default order). */
export function choicesFromProfile(saved: string[]): SectionChoice[] {
  const known = new Set(SECTIONS.map(s => s.id))
  const chosen = saved.filter((id, i) => known.has(id) && saved.indexOf(id) === i)
  if (chosen.length === 0) return SECTIONS.map(s => ({ id: s.id, enabled: true }))
  const rest = SECTIONS.map(s => s.id).filter(id => !chosen.includes(id))
  return keepPricingAfterScope([
    ...chosen.map(id => ({ id, enabled: true })),
    ...rest.map(id => ({ id, enabled: false })),
  ])
}

/** What to save: the enabled sections in order, or nothing when the default (all) is unchanged. */
export function choicesToProfile(choices: SectionChoice[]): string[] {
  const ordered = keepPricingAfterScope(choices)
  const defaults = SECTIONS.map(s => s.id)
  const enabled = ordered.filter(c => c.enabled).map(c => c.id)
  return enabled.length === defaults.length && enabled.every((id, i) => id === defaults[i]) ? [] : enabled
}

export function moveChoice(choices: SectionChoice[], index: number, delta: -1 | 1): SectionChoice[] {
  const target = index + delta
  if (target < 0 || target >= choices.length) return choices
  const result = [...choices]
  const [moved] = result.splice(index, 1)
  result.splice(target, 0, moved!)
  return keepPricingAfterScope(result)
}

export function sectionLabel(id: string): string {
  return SECTIONS.find(s => s.id === id)?.label ?? id
}

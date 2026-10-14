/** The proposal sections in their default order. Their names (`sections.<id>`) are messages. */
export const SECTION_IDS = [
  'summary',
  'problem',
  'scope',
  'deliverables',
  'out_of_scope',
  'timeline',
  'open_questions',
  'investment',
  'terms',
] as const

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
  const known = new Set<string>(SECTION_IDS)
  const chosen = saved.filter((id, i) => known.has(id) && saved.indexOf(id) === i)
  if (chosen.length === 0) return SECTION_IDS.map(id => ({ id, enabled: true }))
  const rest = SECTION_IDS.filter(id => !chosen.includes(id))
  return keepPricingAfterScope([
    ...chosen.map(id => ({ id, enabled: true })),
    ...rest.map(id => ({ id, enabled: false })),
  ])
}

/** What to save: the enabled sections in order, or nothing when the default (all) is unchanged. */
export function choicesToProfile(choices: SectionChoice[]): string[] {
  const ordered = keepPricingAfterScope(choices)
  const defaults: string[] = [...SECTION_IDS]
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

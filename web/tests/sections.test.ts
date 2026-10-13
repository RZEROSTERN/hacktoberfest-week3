import { describe, expect, it } from 'vitest'
import { choicesFromProfile, choicesToProfile, keepPricingAfterScope, moveChoice, SECTIONS } from '../app/utils/sections'

const ids = (choices: { id: string }[]) => choices.map(c => c.id)

describe('choicesFromProfile', () => {
  it('shows every section, in the default order, when nothing is saved', () => {
    const choices = choicesFromProfile([])
    expect(ids(choices)).toEqual(SECTIONS.map(s => s.id))
    expect(choices.every(c => c.enabled)).toBe(true)
  })

  it('puts the saved sections first and in order, and leaves the rest unticked', () => {
    const choices = choicesFromProfile(['scope', 'summary', 'terms'])
    expect(ids(choices).slice(0, 3)).toEqual(['scope', 'summary', 'terms'])
    expect(choices.filter(c => c.enabled).map(c => c.id)).toEqual(['scope', 'summary', 'terms'])
    expect(choices).toHaveLength(SECTIONS.length)
  })

  it('ignores unknown and repeated ids', () => {
    const choices = choicesFromProfile(['summary', 'gossip', 'summary'])
    expect(choices.filter(c => c.enabled).map(c => c.id)).toEqual(['summary'])
  })
})

describe('choicesToProfile', () => {
  it('saves nothing when all sections are on in the default order', () => {
    expect(choicesToProfile(choicesFromProfile([]))).toEqual([])
  })

  it('saves the enabled sections in order', () => {
    const choices = moveChoice(choicesFromProfile([]), 0, 1) // summary down one
    choices.find(c => c.id === 'terms')!.enabled = false
    expect(choicesToProfile(choices)).toEqual(['problem', 'summary', 'scope', 'deliverables', 'out_of_scope', 'timeline', 'open_questions', 'investment'])
  })
})

describe('pricing always comes after the scope', () => {
  it('moves investment back below scope', () => {
    const result = keepPricingAfterScope([
      { id: 'investment', enabled: true },
      { id: 'summary', enabled: true },
      { id: 'scope', enabled: true },
      { id: 'terms', enabled: true },
    ])
    expect(ids(result)).toEqual(['summary', 'scope', 'investment', 'terms'])
  })

  it('stops the user dragging investment above scope', () => {
    const start = choicesFromProfile([])
    const investment = start.findIndex(c => c.id === 'investment')
    let moved = start
    for (let i = 0; i < investment; i++) moved = moveChoice(moved, investment - i, -1)
    const order = ids(moved)
    expect(order.indexOf('investment')).toBeGreaterThan(order.indexOf('scope'))
  })

  it('does nothing at the edges of the list', () => {
    const start = choicesFromProfile([])
    expect(moveChoice(start, 0, -1)).toBe(start)
    expect(moveChoice(start, start.length - 1, 1)).toBe(start)
  })
})

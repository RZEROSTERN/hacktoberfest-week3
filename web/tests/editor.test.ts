import { describe, expect, it } from 'vitest'
import type { ProposalSection } from '../app/types/api'
import { cloneSections, effectiveAssumption, filenameFromDisposition, isDirty, newItem, toPayload } from '../app/utils/editor'

const source = (id: number) => ({ segment_id: id, start: id * 10, end: id * 10 + 5, text: `línea ${id}` })

const sections = (): ProposalSection[] => [
  { id: 'summary', title: 'Resumen', text: 'Un resumen.', lines: [], items: [], items_label: null },
  {
    id: 'scope',
    title: 'Alcance',
    text: '',
    lines: [],
    items: [
      { text: 'Reservaciones', assumption: false, sources: [source(2)] },
      { text: 'Blog', assumption: true, sources: [] },
    ],
    items_label: null,
  },
  { id: 'open_questions', title: 'Preguntas', text: '', lines: ['¿Fotos?', ''], items: [], items_label: null },
  {
    id: 'investment',
    title: 'Inversión',
    text: 'El precio depende del alcance.',
    lines: ['650 MXN por hora'],
    items: [{ text: 'Unos 8 mil', assumption: false, sources: [source(5)] }],
    items_label: 'Presupuesto mencionado:',
  },
]

describe('toPayload', () => {
  it('sends text sections as text, items with their source ids, and lines without blanks', () => {
    const payload = toPayload(sections())
    expect(payload[0]).toEqual({ id: 'summary', text: 'Un resumen.' })
    expect(payload[1]).toEqual({
      id: 'scope',
      items: [
        { text: 'Reservaciones', assumption: false, segment_ids: [2] },
        { text: 'Blog', assumption: true, segment_ids: [] },
      ],
    })
    expect(payload[2]).toEqual({ id: 'open_questions', lines: ['¿Fotos?'] })
    expect(payload[3]).toEqual({
      id: 'investment',
      text: 'El precio depende del alcance.',
      lines: ['650 MXN por hora'],
      items: [{ text: 'Unos 8 mil', assumption: false, segment_ids: [5] }],
    })
  })

  it('drops items with no text', () => {
    const s = sections()
    s[1]!.items.push(newItem())
    expect(toPayload(s)[1]!.items).toHaveLength(2)
  })

  it('never sends an item without a source as confirmed', () => {
    const s = sections()
    s[1]!.items[1]!.assumption = false
    expect(toPayload(s)[1]!.items![1]!.assumption).toBe(true)
  })
})

describe('items written by the user', () => {
  it('start as assumptions because the call does not support them', () => {
    expect(newItem()).toEqual({ text: '', assumption: true, sources: [] })
    expect(effectiveAssumption({ text: 'x', assumption: false, sources: [] })).toBe(true)
    expect(effectiveAssumption({ text: 'x', assumption: false, sources: [source(1)] })).toBe(false)
  })
})

describe('isDirty', () => {
  it('is false for an untouched copy and true after any edit', () => {
    const original = sections()
    const copy = cloneSections(original)
    expect(isDirty(original, copy)).toBe(false)
    copy[0]!.text = 'Otro resumen.'
    expect(isDirty(original, copy)).toBe(true)
  })

  it('ignores a blank new item and blank lines', () => {
    const original = sections()
    const copy = cloneSections(original)
    copy[1]!.items.push(newItem())
    copy[2]!.lines.push('  ')
    expect(isDirty(original, copy)).toBe(false)
  })

  it('does not change the original when the copy is edited', () => {
    const original = sections()
    const copy = cloneSections(original)
    copy[1]!.items[0]!.text = 'cambiado'
    expect(original[1]!.items[0]!.text).toBe('Reservaciones')
  })
})

describe('filenameFromDisposition', () => {
  it('reads the file name the api chose', () => {
    expect(filenameFromDisposition('attachment; filename="propuesta-kevin.pdf"', 'x.pdf')).toBe('propuesta-kevin.pdf')
  })

  it('falls back when there is no header', () => {
    expect(filenameFromDisposition(null, 'proposal.md')).toBe('proposal.md')
    expect(filenameFromDisposition('attachment', 'proposal.md')).toBe('proposal.md')
  })
})

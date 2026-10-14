import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { parseNotices } from '~/utils/notices'

describe('parseNotices', () => {
  it('splits sections and paragraphs, dropping the page title', () => {
    const raw = '# Title\n\nIntro.\n\n## One\n\nFirst.\n\nSecond.\n\n## Two\n\n- a\n- b\n'
    expect(parseNotices(raw)).toEqual([
      { title: 'One', paragraphs: ['First.', 'Second.'] },
      { title: 'Two', paragraphs: ['- a\n- b'] },
    ])
  })

  it('reads the real notices file and names every engine the app ships', () => {
    const file = fileURLToPath(new URL('../../THIRD_PARTY_NOTICES.md', import.meta.url))
    const titles = parseNotices(readFileSync(file, 'utf8')).map(s => s.title)
    for (const name of ['Ollama', 'whisper.cpp', 'Whisper', 'Language models', 'Electron', 'Python']) {
      expect(titles.some(t => t.includes(name)), name).toBe(true)
    }
    const text = readFileSync(file, 'utf8')
    expect(text).toContain('Gemma 4')
    expect(text).toContain('Apache License 2.0')
  })
})

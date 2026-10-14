import { describe, expect, it } from 'vitest'
import type { LlmChoice, Recommended } from '../app/types/api'
import { CUSTOM, defaultSelection, diskNeeded, downloadSize, effectiveModel, enoughDisk, isOpenWithoutModels, modelMessageKey, ramWarning } from '../app/utils/setup'

const choice = (over: Partial<LlmChoice>): LlmChoice => ({
  model: 'gemma4:e4b',
  title: 'Gemma 4 E4B',
  recommended: true,
  size_bytes: 6_600_000_000,
  size_exact: false,
  ram_gb: 8,
  license: 'Apache 2.0',
  note: '',
  not_recommended_for_this_computer: false,
  installed: false,
  ...over,
})

const data = (over: Partial<Recommended> = {}): Recommended => ({
  version: 1,
  updated: '2026-10-13',
  system: { total_ram_bytes: 16 * 2 ** 30, free_disk_bytes: 40_000_000_000 },
  whisper: { id: 'w', title: 'Whisper', size_bytes: 574_000_000, license: 'MIT', note: '', state: 'missing', bytes_on_disk: 0 },
  llm: [choice({}), choice({ model: 'qwen3.5:4b', recommended: false, size_bytes: 3_300_000_000 })],
  margin_bytes: 1_073_741_824,
  library_url: 'https://ollama.com/library',
  ...over,
})

describe('selection', () => {
  it('preselects the recommended model', () => {
    expect(defaultSelection(data().llm)).toEqual({ choice: 'gemma4:e4b', custom: '' })
  })

  it('uses the typed name for a custom model, trimmed', () => {
    expect(effectiveModel({ choice: CUSTOM, custom: '  llama3.2:3b ' })).toBe('llama3.2:3b')
    expect(effectiveModel({ choice: 'qwen3.5:4b', custom: 'ignored' })).toBe('qwen3.5:4b')
  })
})

describe('download size and disk space', () => {
  it('adds the speech model to the language model', () => {
    expect(downloadSize({ choice: 'gemma4:e4b', custom: '' }, data())).toEqual({ bytes: 7_174_000_000, known: true })
  })

  it('skips what is already on the computer, and counts a partial download only for what is left', () => {
    const installed = data({ llm: [choice({ installed: true })] })
    expect(downloadSize({ choice: 'gemma4:e4b', custom: '' }, installed).bytes).toBe(574_000_000)
    const partial = data({ whisper: { ...data().whisper, state: 'partial', bytes_on_disk: 500_000_000 } })
    expect(downloadSize({ choice: 'qwen3.5:4b', custom: '' }, partial).bytes).toBe(3_300_000_000 + 74_000_000)
    const done = data({ whisper: { ...data().whisper, state: 'ready', bytes_on_disk: 574_000_000 } })
    expect(downloadSize({ choice: 'qwen3.5:4b', custom: '' }, done).bytes).toBe(3_300_000_000)
  })

  it('says when a custom model has an unknown size', () => {
    expect(downloadSize({ choice: CUSTOM, custom: 'x:1b' }, data())).toEqual({ bytes: 574_000_000, known: false })
  })

  it('needs room for the downloads plus a margin', () => {
    const size = downloadSize({ choice: 'gemma4:e4b', custom: '' }, data())
    expect(diskNeeded(size, 1_073_741_824)).toBe(7_174_000_000 + 1_073_741_824)
    expect(enoughDisk(size, data())).toBe(true)
    expect(enoughDisk(size, data({ system: { total_ram_bytes: 1, free_disk_bytes: 7_500_000_000 } }))).toBe(false)
  })
})

describe('ramWarning', () => {
  it('warns only for models that need more memory than the computer has', () => {
    expect(ramWarning(choice({}), 16 * 2 ** 30)).toBeNull()
    const big = choice({ not_recommended_for_this_computer: true, ram_gb: 24 })
    expect(ramWarning(big, 16 * 2 ** 30)).toEqual({ need: 24, have: 16 })
  })
})

describe('isOpenWithoutModels', () => {
  it('lets the wizard and the license notices through before the models exist', () => {
    expect(isOpenWithoutModels('/setup')).toBe(true)
    expect(isOpenWithoutModels('/notices')).toBe(true)
  })

  it('holds everything else back', () => {
    for (const path of ['/', '/new', '/profile', '/settings', '/calls/abc', '/notices/x']) {
      expect(isOpenWithoutModels(path), path).toBe(false)
    }
  })
})

describe('modelMessageKey', () => {
  it('turns a model name into the key of its translated description', () => {
    expect(modelMessageKey('gemma4:e4b')).toBe('models.gemma4_e4b')
    expect(modelMessageKey('mistral-nemo:12b')).toBe('models.mistral_nemo_12b')
    expect(modelMessageKey('whisper')).toBe('models.whisper')
  })
})

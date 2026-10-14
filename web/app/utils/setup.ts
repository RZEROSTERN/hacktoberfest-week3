import type { LlmChoice, Recommended } from '~/types/api'

export const CUSTOM = '__custom__'

/** What the user picked: one of the tested models, or a name typed under "Advanced". */
export interface ModelSelection {
  choice: string
  custom: string
}

export function defaultSelection(choices: LlmChoice[]): ModelSelection {
  const best = choices.find(c => c.recommended) ?? choices[0]
  return { choice: best?.model ?? '', custom: '' }
}

/** The Ollama model name that will be downloaded. */
export function effectiveModel(selection: ModelSelection): string {
  return selection.choice === CUSTOM ? selection.custom.trim() : selection.choice
}

export interface DownloadSize {
  /** Bytes still to download. */
  bytes: number
  /** False for a model we have not tested: its size is only known once the download starts. */
  known: boolean
}

export function downloadSize(selection: ModelSelection, data: Recommended): DownloadSize {
  const whisper = data.whisper.state === 'ready' ? 0 : data.whisper.size_bytes - data.whisper.bytes_on_disk
  if (selection.choice === CUSTOM) return { bytes: whisper, known: false }
  const model = data.llm.find(c => c.model === selection.choice)
  return { bytes: (model && !model.installed ? model.size_bytes : 0) + whisper, known: true }
}

export function diskNeeded(size: DownloadSize, marginBytes: number): number {
  return size.bytes + marginBytes
}

export function enoughDisk(size: DownloadSize, data: Recommended): boolean {
  return data.system.free_disk_bytes >= diskNeeded(size, data.margin_bytes)
}

/** The values for the memory warning of a model that needs more than this computer has; null when it is fine. */
export function ramWarning(choice: LlmChoice, totalRamBytes: number): { need: number, have: number } | null {
  if (!choice.not_recommended_for_this_computer) return null
  return { need: choice.ram_gb, have: Math.round(totalRamBytes / 2 ** 30) }
}

/** The key of a model's translated description: `gemma4:e4b` -> `models.gemma4_e4b`. */
export function modelMessageKey(model: string): string {
  return `models.${model.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')}`
}

/** Pages that need no models, so the route guard lets them through: the wizard and static information. */
const OPEN_PAGES = new Set(['/setup', '/notices'])

export function isOpenWithoutModels(path: string): boolean {
  return OPEN_PAGES.has(path)
}

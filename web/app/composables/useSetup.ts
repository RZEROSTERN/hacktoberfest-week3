import type { ModelsInfo, Recommended, SetupProgress, SetupState, SetupStatus } from '~/types/api'
import { apiErrorMessage } from '~/utils/format'

export const TERMINAL_STATES: SetupState[] = ['idle', 'paused', 'failed', 'compat_failed', 'interrupted', 'done']

/** Talking to the setup endpoints: status, the model list, starting, pausing and following a run. */
export function useSetup() {
  const { base, apiFetch } = useApi()

  const status = () => apiFetch<SetupStatus>('/setup/status')
  const recommended = () => apiFetch<Recommended>('/setup/recommended')
  const progress = () => apiFetch<SetupProgress>('/setup/progress')
  const models = () => apiFetch<ModelsInfo>('/models')

  async function post<T>(path: string, body?: object): Promise<T> {
    return apiFetch<T>(path, { method: 'POST', body })
  }

  const start = (model: string) => post<SetupProgress>('/setup/start', { model })
  const pause = () => post<SetupProgress>('/setup/pause')
  const resume = () => post<SetupProgress>('/setup/resume')
  const activate = (model: string) => post<ModelsInfo>('/models/llm/activate', { model })
  const removeModel = async (name: string) => {
    await apiFetch(`/models/llm/${encodeURIComponent(name)}`, { method: 'DELETE' })
  }
  const removeWhisper = async () => {
    await apiFetch('/models/whisper', { method: 'DELETE' })
  }

  /**
   * Follow a run with Server-Sent Events. Calls `onUpdate` for every change and stops by itself when
   * the run ends. If the stream cannot be opened it falls back to asking every two seconds.
   */
  function follow(onUpdate: (p: SetupProgress) => void): () => void {
    let closed = false
    let source: EventSource | null = null
    let timer: ReturnType<typeof setInterval> | undefined

    function stop() {
      closed = true
      source?.close()
      if (timer !== undefined) clearInterval(timer)
    }

    function poll() {
      timer = setInterval(async () => {
        try {
          const p = await progress()
          onUpdate(p)
          if (TERMINAL_STATES.includes(p.state)) stop()
        } catch {
          // the engine may be restarting: keep trying
        }
      }, 2000)
    }

    if (typeof EventSource === 'undefined') {
      poll()
    } else {
      source = new EventSource(`${base}/setup/events`)
      source.addEventListener('progress', (event) => {
        const p = JSON.parse((event as MessageEvent<string>).data) as SetupProgress
        onUpdate(p)
        if (TERMINAL_STATES.includes(p.state)) stop()
      })
      source.onerror = () => {
        if (closed) return
        source?.close()
        source = null
        poll()
      }
    }
    return stop
  }

  return { status, recommended, progress, models, start, pause, resume, activate, removeModel, removeWhisper, follow, apiErrorMessage }
}

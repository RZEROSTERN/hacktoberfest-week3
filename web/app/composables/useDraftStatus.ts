import type { Draft } from '~/types/api'
import { apiErrorMessage, isDraftActive } from '~/utils/format'

/** Follows the proposal draft of one call: starts it, polls while it runs, and can cancel it. */
export function useDraftStatus(callId: string) {
  const { apiFetch } = useApi()
  const draft = ref<Draft | null>(null)
  const error = ref<string | null>(null)

  const poller = usePoller(async () => {
    try {
      draft.value = await apiFetch<Draft>(`/calls/${callId}/draft`)
      error.value = null
      return isDraftActive(draft.value.status)
    } catch (e) {
      if ((e as { statusCode?: number }).statusCode === 404) return false // no draft yet
      error.value = 'Could not reach the local engine. Is the app still running?'
      return false
    }
  })

  async function start(language: string | null) {
    error.value = null
    try {
      draft.value = await apiFetch<Draft>(`/calls/${callId}/draft`, {
        method: 'POST',
        body: language ? { language } : {},
      })
      poller.start()
    } catch (e) {
      error.value = apiErrorMessage(e, 'The draft could not be started.')
    }
  }

  async function cancel() {
    try {
      draft.value = await apiFetch<Draft>(`/calls/${callId}/draft/cancel`, { method: 'POST' })
    } catch (e) {
      error.value = apiErrorMessage(e, 'Could not cancel the draft.')
    }
  }

  onMounted(poller.start)
  return { draft, error, start, cancel }
}

import type { Draft, SectionEdit } from '~/types/api'
import { filenameFromDisposition } from '~/utils/editor'
import { parseErrorBody, readApiError } from '~/utils/apiError'
import { isDraftActive } from '~/utils/format'

/** Follows the proposal draft of one call: starts it, polls while it runs, and can cancel it. */
export function useDraftStatus(callId: string) {
  const { base, apiFetch } = useApi()
  const errors = useErrors()
  const { t } = useFormat()
  const draft = ref<Draft | null>(null)
  const error = ref<string | null>(null)

  const poller = usePoller(async () => {
    try {
      draft.value = await apiFetch<Draft>(`/calls/${callId}/draft`)
      error.value = null
      return isDraftActive(draft.value.status)
    } catch (e) {
      if ((e as { statusCode?: number }).statusCode === 404) return false // no draft yet
      error.value = t('errors.engineUnreachable')
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
      error.value = errors.message(e, 'errors.draftStart')
    }
  }

  async function cancel() {
    try {
      draft.value = await apiFetch<Draft>(`/calls/${callId}/draft/cancel`, { method: 'POST' })
    } catch (e) {
      error.value = errors.message(e, 'errors.draftCancel')
    }
  }

  /** Save the user's edits. Returns false (and sets `error`) when the api refuses them. */
  async function saveEdits(sections: SectionEdit[]): Promise<boolean> {
    error.value = null
    try {
      draft.value = await apiFetch<Draft>(`/calls/${callId}/draft/proposal`, { method: 'PUT', body: { sections } })
      return true
    } catch (e) {
      error.value = errors.message(e, 'errors.draftSave')
      return false
    }
  }

  /** Download the saved proposal. Fetched (not linked) so a refusal shows a message instead of raw JSON. */
  async function download(format: 'md' | 'pdf') {
    error.value = null
    try {
      const response = await $fetch.raw<Blob>(`${base}/calls/${callId}/draft/export`, {
        query: { format },
        responseType: 'blob',
      })
      const name = filenameFromDisposition(response.headers.get('content-disposition'), `proposal.${format}`)
      const url = URL.createObjectURL(response._data as Blob)
      const link = document.createElement('a')
      link.href = url
      link.download = name
      document.body.appendChild(link)
      link.click()
      link.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (e) {
      error.value = errors.fromInfo(await exportErrorInfo(e), 'errors.export')
    }
  }

  onMounted(poller.start)
  return { draft, error, start, cancel, saveEdits, download }
}

/** With `responseType: 'blob'` an error body arrives as a Blob: read the api's answer from it. */
async function exportErrorInfo(error: unknown) {
  const info = readApiError(error)
  const data = (error as { data?: unknown }).data
  if (data instanceof Blob) {
    try {
      return parseErrorBody(JSON.parse(await data.text()), info.status)
    } catch {
      // not JSON: use the generic message
    }
  }
  return info
}

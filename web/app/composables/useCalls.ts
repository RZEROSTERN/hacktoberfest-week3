import type { Call, Transcript } from '~/types/api'
import { parseErrorBody, UploadError } from '~/utils/apiError'

export interface Upload {
  promise: Promise<Call>
  abort: () => void
}

function answerOf(xhr: XMLHttpRequest) {
  try {
    return parseErrorBody(JSON.parse(xhr.responseText), xhr.status)
  } catch {
    return parseErrorBody(null, xhr.status)
  }
}

export function useCalls() {
  const { base, apiFetch } = useApi()

  /** Uploads with XMLHttpRequest because fetch cannot report upload progress. */
  function upload(file: File, keepAudio: boolean, onProgress: (fraction: number) => void): Upload {
    const xhr = new XMLHttpRequest()
    const promise = new Promise<Call>((resolve, reject) => {
      xhr.open('POST', `${base}/calls`)
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) onProgress(event.loaded / event.total)
      }
      xhr.onload = () => {
        if (xhr.status === 202) resolve(JSON.parse(xhr.responseText) as Call)
        else reject(new UploadError(answerOf(xhr)))
      }
      xhr.onerror = () => reject(new UploadError(parseErrorBody(null, 0), 'unreachable'))
      xhr.onabort = () => reject(new UploadError(parseErrorBody(null, 0), 'cancelled'))
      const form = new FormData()
      form.append('file', file)
      form.append('keep_audio', String(keepAudio))
      xhr.send(form)
    })
    return { promise, abort: () => xhr.abort() }
  }

  return {
    upload,
    list: () => apiFetch<Call[]>('/calls'),
    get: (id: string) => apiFetch<Call>(`/calls/${id}`),
    transcript: (id: string) => apiFetch<Transcript>(`/calls/${id}/transcript`),
    cancel: (id: string) => apiFetch<Call>(`/calls/${id}/cancel`, { method: 'POST' }),
    retry: (id: string) => apiFetch<Call>(`/calls/${id}/retry`, { method: 'POST' }),
    remove: async (id: string) => {
      await apiFetch(`/calls/${id}`, { method: 'DELETE' })
    },
  }
}

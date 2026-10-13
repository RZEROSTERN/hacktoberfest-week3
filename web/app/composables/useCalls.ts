import type { Call, Transcript } from '~/types/api'
import { uploadErrorMessage } from '~/utils/format'

export interface Upload {
  promise: Promise<Call>
  abort: () => void
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
        else reject(new Error(uploadErrorMessage(xhr.status, xhr.responseText)))
      }
      xhr.onerror = () => reject(new Error(uploadErrorMessage(0, '')))
      xhr.onabort = () => reject(new Error('Upload cancelled.'))
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

import type { Call, Transcript } from '~/types/api'
import { isActive } from '~/utils/format'

/** Follows one call: polls while its job is running and loads the transcript once it is done. */
export function useCallStatus(id: string) {
  const api = useCalls()
  const call = ref<Call | null>(null)
  const transcript = ref<Transcript | null>(null)
  const loadError = ref<string | null>(null)
  let timer: ReturnType<typeof setInterval> | undefined

  async function refresh() {
    try {
      call.value = await api.get(id)
      loadError.value = null
      if (call.value.status === 'done' && !transcript.value) transcript.value = await api.transcript(id)
      if (!isActive(call.value.status)) stop()
    } catch {
      loadError.value = 'Could not reach the local engine. Is the app still running?'
    }
  }

  function start() {
    stop()
    void refresh()
    timer = setInterval(() => void refresh(), 1000)
  }

  function stop() {
    if (timer !== undefined) clearInterval(timer)
    timer = undefined
  }

  async function cancel() {
    call.value = await api.cancel(id)
  }

  async function retry() {
    call.value = await api.retry(id)
    start()
  }

  onMounted(start)
  onBeforeUnmount(stop)

  return { call, transcript, loadError, cancel, retry }
}

/** Calls `tick` every `ms` while mounted; `tick` returns false to stop. */
export function usePoller(tick: () => Promise<boolean>, ms = 1000) {
  let timer: ReturnType<typeof setInterval> | undefined

  function stop() {
    if (timer !== undefined) clearInterval(timer)
    timer = undefined
  }

  async function run() {
    if (!(await tick())) stop()
  }

  function start() {
    stop()
    void run()
    timer = setInterval(() => void run(), ms)
  }

  onBeforeUnmount(stop)
  return { start, stop }
}

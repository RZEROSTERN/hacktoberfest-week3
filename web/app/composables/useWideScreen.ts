/** True while the window is at least `minWidth` px wide, and follows resizing. False until the page is mounted. */
export function useWideScreen(minWidth = 1100) {
  const wide = ref(false)
  let query: MediaQueryList | null = null

  function update() {
    wide.value = query?.matches ?? false
  }

  onMounted(() => {
    query = window.matchMedia(`(min-width: ${minWidth}px)`)
    update()
    query.addEventListener('change', update)
  })
  onBeforeUnmount(() => query?.removeEventListener('change', update))

  return wide
}

import { isOpenWithoutModels } from '~/utils/setup'

/** Until the models are downloaded and checked, nothing else in the app works: send everything to /setup. */
export default defineNuxtRouteMiddleware(async (to) => {
  if (isOpenWithoutModels(to.path)) return
  const ready = useState<boolean | null>('setupReady', () => null)
  if (ready.value === true) return
  const { status } = useSetup()
  try {
    ready.value = (await status()).ready
  } catch {
    ready.value = false // the engine is not answering: the setup page explains it
  }
  if (!ready.value) return navigateTo('/setup')
})

<script setup lang="ts">
import type { Recommended, SetupProgress, SetupStatus } from '~/types/api'
import { defaultSelection, effectiveModel, type ModelSelection } from '~/utils/setup'

const setup = useSetup()
const ready = useState<boolean | null>('setupReady', () => null)

const status = ref<SetupStatus | null>(null)
const data = ref<Recommended | null>(null)
const progress = ref<SetupProgress | null>(null)
const selection = ref<ModelSelection>({ choice: '', custom: '' })
const loadError = ref<string | null>(null)
const startError = ref<string | null>(null)
const starting = ref(false)
const pausing = ref(false)
const later = ref(false) // the user chose "Not now"
const chooseAgain = ref(false) // after a failed check: back to the model list
const sawRun = ref(false) // a run was active in this visit
let stopFollowing: (() => void) | null = null

async function load() {
  loadError.value = null
  try {
    const [s, r, p] = await Promise.all([setup.status(), setup.recommended(), setup.progress()])
    status.value = s
    data.value = r
    progress.value = p
    ready.value = s.ready
    if (!selection.value.choice) selection.value = defaultSelection(r.llm)
    if (p.state === 'running') follow()
  } catch {
    loadError.value = 'Could not reach the local engine. Is the app still running?'
  }
}

function follow() {
  stopFollowing?.()
  stopFollowing = setup.follow(async (p) => {
    progress.value = p
    if (p.state === 'running') sawRun.value = true
    else pausing.value = false
    if (p.state === 'done' || p.state === 'failed' || p.state === 'compat_failed') await refreshStatus()
  })
}

async function refreshStatus() {
  try {
    status.value = await setup.status()
    ready.value = status.value.ready
  } catch {
    // keep the last known status
  }
}

onMounted(load)
onBeforeUnmount(() => stopFollowing?.())

/** What to show. A leftover "done" or "failed" from an old run is ignored once the app is ready. */
const view = computed(() => {
  if (loadError.value) return 'error'
  if (!status.value || !data.value || !progress.value) return 'loading'
  if (status.value.problem) return 'engine'
  const state = progress.value.state
  if (state === 'running') return 'progress'
  if (status.value.ready && !sawRun.value) return 'home'
  if ((state === 'compat_failed' || state === 'failed') && chooseAgain.value) return later.value ? 'later' : 'request'
  if (state === 'done' && sawRun.value) return 'progress'
  if (state === 'done' && !status.value.ready) return later.value ? 'later' : 'request'
  if (['paused', 'failed', 'interrupted', 'compat_failed'].includes(state)) return later.value ? 'later' : 'progress'
  return later.value ? 'later' : 'request'
})

watch(view, (v) => {
  if (v === 'home') void navigateTo('/')
})

const recommended = computed(() => {
  const best = data.value?.llm.find(c => c.recommended)
  return best ? { model: best.model, title: best.title } : null
})

async function begin(model: string) {
  starting.value = true
  startError.value = null
  try {
    progress.value = await setup.start(model)
    sawRun.value = true
    chooseAgain.value = false
    later.value = false
    follow()
  } catch (e) {
    startError.value = setup.apiErrorMessage(e, 'The download could not be started.')
  } finally {
    starting.value = false
  }
}

async function onResume() {
  later.value = false
  try {
    progress.value = await setup.resume()
    sawRun.value = true
    follow()
  } catch (e) {
    startError.value = setup.apiErrorMessage(e, 'The download could not be resumed.')
  }
}

async function onPause() {
  pausing.value = true
  progress.value = await setup.pause()
}

function useRecommended() {
  if (recommended.value) void begin(recommended.value.model)
}

async function finish() {
  await refreshStatus()
  await navigateTo('/')
}
</script>

<template>
  <section>
    <p
      v-if="view === 'loading'"
      class="muted"
    >
      Loading…
    </p>

    <div
      v-else-if="view === 'error' || view === 'engine'"
      role="alert"
    >
      <h1>PostCall can't start its AI engine</h1>
      <p class="error">
        {{ loadError ?? status?.problem_message }}
      </p>
      <p class="muted">
        Close and reopen PostCall. If it keeps happening, restart your computer.
      </p>
      <button
        class="button"
        @click="load"
      >
        Try again
      </button>
    </div>

    <div v-else-if="view === 'later'">
      <h1>PostCall needs its models</h1>
      <p>
        Nothing in PostCall works until the AI models are on this computer. You will be asked again the next time you open it.
      </p>
      <button
        class="button"
        @click="later = false"
      >
        Download models
      </button>
    </div>

    <SetupRequest
      v-else-if="view === 'request' && data"
      v-model="selection"
      :data="data"
      :starting="starting"
      :error="startError"
      @start="begin(effectiveModel(selection))"
      @later="later = true"
    />

    <template v-else-if="view === 'progress' && progress">
      <SetupProgress
        :progress="progress"
        :recommended="recommended"
        :pausing="pausing"
        @pause="onPause"
        @resume="onResume"
        @later="later = true"
        @recommended="useRecommended"
        @choose="chooseAgain = true"
        @done="finish"
      />
      <p
        v-if="startError"
        class="error"
        role="alert"
      >
        {{ startError }}
      </p>
    </template>
  </section>
</template>

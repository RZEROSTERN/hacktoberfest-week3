<script setup lang="ts">
import type { ModelsInfo, Recommended } from '~/types/api'
import { formatBytes, formatMemory } from '~/utils/bytes'
import { defaultSelection, effectiveModel, type ModelSelection } from '~/utils/setup'

const setup = useSetup()
const ready = useState<boolean | null>('setupReady', () => null)

const info = ref<ModelsInfo | null>(null)
const data = ref<Recommended | null>(null)
const selection = ref<ModelSelection>({ choice: '', custom: '' })
const loadError = ref<string | null>(null)
const error = ref<string | null>(null)
const busy = ref(false)

async function load() {
  try {
    const [models, recommended] = await Promise.all([setup.models(), setup.recommended()])
    info.value = models
    data.value = recommended
    if (!selection.value.choice) selection.value = defaultSelection(recommended.llm)
    loadError.value = null
  } catch {
    loadError.value = 'Could not reach the local engine. Is the app still running?'
  }
}

onMounted(load)

// The model in use first, then by name.
const models = computed(() =>
  [...(info.value?.llm ?? [])].sort((a, b) => Number(b.active) - Number(a.active) || a.name.localeCompare(b.name)),
)

async function run(action: () => Promise<unknown>, fallback: string) {
  busy.value = true
  error.value = null
  try {
    await action()
    await load()
  } catch (e) {
    error.value = setup.apiErrorMessage(e, fallback)
  } finally {
    busy.value = false
  }
}

const use = (name: string) => run(() => setup.activate(name), 'That model could not be selected.')

async function remove(name: string) {
  if (!window.confirm(`Delete ${name} from this computer? It frees disk space; you can download it again later.`)) return
  await run(() => setup.removeModel(name), 'The model could not be deleted.')
}

async function removeWhisper() {
  if (!window.confirm('Delete the speech model? Transcription stops working until it is downloaded again.')) return
  await run(() => setup.removeWhisper(), 'The speech model could not be deleted.')
  ready.value = false
  await navigateTo('/setup')
}

/** A model that has not been checked on this computer, or a new one: same flow as the first launch. */
async function startSetup(model: string) {
  busy.value = true
  error.value = null
  try {
    await setup.start(model)
    await navigateTo('/setup')
  } catch (e) {
    error.value = setup.apiErrorMessage(e, 'The download could not be started.')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section>
    <h1>Settings</h1>
    <p
      v-if="loadError"
      class="error"
      role="alert"
    >
      {{ loadError }}
    </p>
    <p
      v-else-if="!info || !data"
      class="muted"
    >
      Loading…
    </p>

    <template v-else>
      <p
        v-if="error"
        class="error"
        role="alert"
      >
        {{ error }}
      </p>

      <div class="page-grid">
        <div>
          <h2>Language models on this computer</h2>
          <p
            v-if="info.llm.length === 0"
            class="muted"
          >
            None yet.
          </p>
          <ul class="models">
            <li
              v-for="model in models"
              :key="model.name"
              :data-model="model.name"
            >
              <div class="grow">
                <strong>{{ model.title ?? model.name }}</strong>
                <span class="muted detail">
                  <template v-if="model.title">{{ model.name }} · </template>{{ formatBytes(model.size_bytes) }}
                </span>
                <span
                  v-if="model.active"
                  class="badge good"
                >In use</span>
                <span
                  v-else-if="!model.compat_ok"
                  class="badge"
                >Not checked yet</span>
                <span
                  v-if="model.cloud"
                  class="badge warn"
                >Cloud model: not allowed</span>
              </div>
              <div class="row">
                <button
                  v-if="!model.active && model.compat_ok && !model.cloud"
                  class="button secondary"
                  :disabled="busy"
                  @click="use(model.name)"
                >
                  Use this model
                </button>
                <button
                  v-else-if="!model.active && !model.cloud"
                  class="button secondary"
                  :disabled="busy"
                  @click="startSetup(model.name)"
                >
                  Check and use
                </button>
                <button
                  v-if="!model.active"
                  class="button secondary"
                  :disabled="busy"
                  @click="remove(model.name)"
                >
                  Delete
                </button>
              </div>
            </li>
          </ul>


          <h2>Speech model</h2>
          <div class="card">
            <p>
              {{ info.whisper.title }} · {{ formatBytes(info.whisper.size_bytes) }} · {{ info.whisper.license }}
              <span
                v-if="info.whisper.state === 'ready'"
                class="badge good"
              >On this computer</span>
              <span
                v-else
                class="badge warn"
              >{{ info.whisper.state === 'partial' ? 'Partly downloaded' : 'Not downloaded' }}</span>
            </p>
            <button
              v-if="info.whisper.state !== 'missing'"
              class="button secondary"
              :disabled="busy"
              @click="removeWhisper"
            >
              Delete
            </button>
          </div>

          <h2>This computer</h2>
          <p class="muted">
            {{ formatMemory(info.system.total_ram_bytes) }} of memory · {{ formatBytes(info.system.free_disk_bytes) }} of free disk space
          </p>
        </div>

        <div>
          <h2>Download another model</h2>
          <ModelPicker
            v-model="selection"
            :data="data"
          />
          <div class="row">
            <button
              class="button"
              :disabled="busy || !effectiveModel(selection)"
              @click="startSetup(effectiveModel(selection))"
            >
              Download and check
            </button>
          </div>

        </div>
      </div>
    </template>
  </section>
</template>

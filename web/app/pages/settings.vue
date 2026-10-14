<script setup lang="ts">
import type { ModelsInfo, Recommended } from '~/types/api'
import { defaultSelection, effectiveModel, type ModelSelection } from '~/utils/setup'

const setup = useSetup()
const errors = useErrors()
const format = useFormat()
const ready = useState<boolean | null>('setupReady', () => null)

const info = ref<ModelsInfo | null>(null)
const data = ref<Recommended | null>(null)
const selection = ref<ModelSelection>({ choice: '', custom: '' })
const unreachable = ref(false)
const error = ref<string | null>(null)
const busy = ref(false)

async function load() {
  try {
    const [models, recommended] = await Promise.all([setup.models(), setup.recommended()])
    info.value = models
    data.value = recommended
    if (!selection.value.choice) selection.value = defaultSelection(recommended.llm)
    unreachable.value = false
  } catch {
    unreachable.value = true
  }
}

onMounted(load)

// The model in use first, then by name.
const models = computed(() =>
  [...(info.value?.llm ?? [])].sort((a, b) => Number(b.active) - Number(a.active) || a.name.localeCompare(b.name)),
)

async function run(action: () => Promise<unknown>, fallbackKey: string) {
  busy.value = true
  error.value = null
  try {
    await action()
    await load()
  } catch (e) {
    error.value = errors.message(e, fallbackKey)
  } finally {
    busy.value = false
  }
}

const use = (name: string) => run(() => setup.activate(name), 'errors.modelSelect')

async function remove(name: string) {
  if (!window.confirm(format.t('settings.confirmDeleteModel', { name }))) return
  await run(() => setup.removeModel(name), 'errors.modelDelete')
}

async function removeWhisper() {
  if (!window.confirm(format.t('settings.confirmDeleteSpeech'))) return
  await run(() => setup.removeWhisper(), 'errors.whisperDelete')
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
    error.value = errors.message(e, 'errors.downloadStart')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section>
    <h1>{{ $t('settings.title') }}</h1>
    <p
      v-if="unreachable"
      class="error"
      role="alert"
    >
      {{ $t('errors.engineUnreachable') }}
    </p>
    <p
      v-else-if="!info || !data"
      class="muted"
    >
      {{ $t('common.loading') }}
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
          <h2>{{ $t('settings.models') }}</h2>
          <p
            v-if="info.llm.length === 0"
            class="muted"
          >
            {{ $t('settings.none') }}
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
                  <template v-if="model.title">{{ model.name }} · </template>{{ format.bytes(model.size_bytes) }}
                </span>
                <span
                  v-if="model.active"
                  class="badge good"
                >{{ $t('settings.inUse') }}</span>
                <span
                  v-else-if="!model.compat_ok"
                  class="badge"
                >{{ $t('settings.notChecked') }}</span>
                <span
                  v-if="model.cloud"
                  class="badge warn"
                >{{ $t('settings.cloud') }}</span>
              </div>
              <div class="row">
                <button
                  v-if="!model.active && model.compat_ok && !model.cloud"
                  class="button secondary"
                  :disabled="busy"
                  @click="use(model.name)"
                >
                  {{ $t('settings.use') }}
                </button>
                <button
                  v-else-if="!model.active && !model.cloud"
                  class="button secondary"
                  :disabled="busy"
                  @click="startSetup(model.name)"
                >
                  {{ $t('settings.checkAndUse') }}
                </button>
                <button
                  v-if="!model.active"
                  class="button secondary"
                  :disabled="busy"
                  @click="remove(model.name)"
                >
                  {{ $t('common.delete') }}
                </button>
              </div>
            </li>
          </ul>


          <h2>{{ $t('settings.speech') }}</h2>
          <div class="card">
            <p>
              {{ info.whisper.title }} · {{ format.bytes(info.whisper.size_bytes) }} · {{ info.whisper.license }}
              <span
                v-if="info.whisper.state === 'ready'"
                class="badge good"
              >{{ $t('settings.speechReady') }}</span>
              <span
                v-else
                class="badge warn"
              >{{ info.whisper.state === 'partial' ? $t('settings.speechPartial') : $t('settings.speechMissing') }}</span>
            </p>
            <button
              v-if="info.whisper.state !== 'missing'"
              class="button secondary"
              :disabled="busy"
              @click="removeWhisper"
            >
              {{ $t('common.delete') }}
            </button>
          </div>

          <h2>{{ $t('settings.computer') }}</h2>
          <p class="muted">
            {{ $t('settings.computerFacts', { memory: format.memory(info.system.total_ram_bytes), disk: format.bytes(info.system.free_disk_bytes) }) }}
          </p>
        </div>

        <div>
          <h2>{{ $t('settings.downloadAnother') }}</h2>
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
              {{ $t('settings.downloadAndCheck') }}
            </button>
          </div>

        </div>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import type { Recommended } from '~/types/api'
import { diskNeeded, downloadSize, effectiveModel, enoughDisk, type ModelSelection } from '~/utils/setup'

const selection = defineModel<ModelSelection>({ required: true })
const format = useFormat()

const props = defineProps<{
  data: Recommended
  starting: boolean
  error: string | null
}>()

defineEmits<{ start: [], later: [] }>()

const size = computed(() => downloadSize(selection.value, props.data))
const roomOk = computed(() => enoughDisk(size.value, props.data))
const chosen = computed(() => effectiveModel(selection.value))
</script>

<template>
  <section>
    <h1>{{ $t('setup.request.title') }}</h1>
    <p>
      {{ $t('setup.request.intro') }}
    </p>

    <div class="page-grid">
      <div>
        <ModelPicker
          v-model="selection"
          :data="data"
        />
      </div>

      <div>
        <div class="card">
          <strong>{{ $t('setup.request.speech') }}</strong>
          <p>
            {{ data.whisper.title }} · {{ format.bytes(data.whisper.size_bytes) }} · {{ data.whisper.license }}
            <span
              v-if="data.whisper.state === 'ready'"
              class="badge"
            >{{ $t('picker.installed') }}</span>
          </p>
          <p class="muted">
            {{ format.modelNote('whisper', data.whisper.note) }}
          </p>
        </div>

        <div class="card">
          <p>
            <strong>{{ $t('setup.request.total') }}</strong>
            {{ format.bytes(size.bytes) }}<span v-if="!size.known"> {{ $t('setup.request.plusModel') }}</span>
          </p>
          <p>
            <strong>{{ $t('setup.request.diskNeeded') }}</strong> {{ format.bytes(diskNeeded(size, data.margin_bytes)) }}
            ({{ $t('setup.request.diskRoom', { margin: format.bytes(data.margin_bytes) }) }}) ·
            <strong>{{ $t('setup.request.diskAvailable') }}</strong> {{ format.bytes(data.system.free_disk_bytes) }}
          </p>
          <p
            v-if="!roomOk"
            class="error"
            role="alert"
          >
            {{ $t('setup.request.noRoom') }}
          </p>
          <p class="muted">
            {{ $t('setup.request.wifi') }}
          </p>
        </div>

        <p
          v-if="error"
          class="error"
          role="alert"
        >
          {{ error }}
        </p>

        <div class="row">
          <button
            class="button"
            :disabled="starting || !chosen || !roomOk"
            @click="$emit('start')"
          >
            {{ starting ? $t('setup.request.starting') : $t('setup.request.download') }}
          </button>
          <button
            class="button secondary"
            :disabled="starting"
            @click="$emit('later')"
          >
            {{ $t('common.notNow') }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

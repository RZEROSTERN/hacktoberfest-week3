<script setup lang="ts">
import type { Recommended } from '~/types/api'
import { formatBytes } from '~/utils/bytes'
import { diskNeeded, downloadSize, effectiveModel, enoughDisk, type ModelSelection } from '~/utils/setup'

const selection = defineModel<ModelSelection>({ required: true })

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
    <h1>Welcome to PostCall</h1>
    <p>
      PostCall works fully offline and keeps your client calls private. For that, the AI models it needs
      are downloaded once to this computer. After this, nothing about your calls ever leaves it.
    </p>

    <ModelPicker
      v-model="selection"
      :data="data"
    />

    <div class="card">
      <strong>Speech model (also downloaded)</strong>
      <p>
        {{ data.whisper.title }} · {{ formatBytes(data.whisper.size_bytes) }} · {{ data.whisper.license }}
        <span
          v-if="data.whisper.state === 'ready'"
          class="badge"
        >Already on this computer</span>
      </p>
      <p class="muted">
        {{ data.whisper.note }}
      </p>
    </div>

    <div class="card">
      <p>
        <strong>Total download:</strong>
        {{ formatBytes(size.bytes) }}<span v-if="!size.known"> plus the size of your model (shown when the download starts)</span>
      </p>
      <p>
        <strong>Free disk space needed:</strong> {{ formatBytes(diskNeeded(size, data.margin_bytes)) }}
        (the downloads plus {{ formatBytes(data.margin_bytes) }} of room) ·
        <strong>Available:</strong> {{ formatBytes(data.system.free_disk_bytes) }}
      </p>
      <p
        v-if="!roomOk"
        class="error"
        role="alert"
      >
        There is not enough free disk space. Free some space or choose a smaller model.
      </p>
      <p class="muted">
        We recommend connecting to Wi-Fi: this is a large download. You can pause it and continue later.
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
        {{ starting ? 'Starting…' : 'Download now' }}
      </button>
      <button
        class="button secondary"
        :disabled="starting"
        @click="$emit('later')"
      >
        Not now
      </button>
    </div>
  </section>
</template>

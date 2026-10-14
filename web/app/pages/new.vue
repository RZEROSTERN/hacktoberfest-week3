<script setup lang="ts">
const api = useCalls()
const errors = useErrors()

const file = ref<File | null>(null)
const keepAudio = ref(false)
const uploading = ref(false)
const uploadProgress = ref(0)
const error = ref<string | null>(null)
let current: ReturnType<typeof api.upload> | null = null

function onPick(event: Event) {
  file.value = (event.target as HTMLInputElement).files?.[0] ?? null
  error.value = null
}

async function start() {
  if (!file.value) return
  uploading.value = true
  uploadProgress.value = 0
  error.value = null
  current = api.upload(file.value, keepAudio.value, (fraction) => {
    uploadProgress.value = fraction
  })
  try {
    const call = await current.promise
    await navigateTo(`/calls/${call.id}`)
  } catch (e) {
    error.value = errors.message(e, 'errors.upload')
  } finally {
    uploading.value = false
    current = null
  }
}

function cancelUpload() {
  current?.abort()
}
</script>

<template>
  <section class="page-narrow">
    <h1>{{ $t('upload.title') }}</h1>
    <p class="muted">
      {{ $t('upload.intro') }}
    </p>

    <ConsentReminder />

    <div class="row">
      <input
        type="file"
        accept=".mp3,.m4a,.wav,.mp4,audio/*,video/mp4"
        :disabled="uploading"
        :aria-label="$t('upload.fileLabel')"
        @change="onPick"
      >
    </div>

    <label class="row">
      <input
        v-model="keepAudio"
        type="checkbox"
        :disabled="uploading"
      >
      {{ $t('upload.keepAudio') }}
    </label>
    <p class="muted">
      {{ $t('upload.keepAudioNote') }}
    </p>

    <ProgressBar
      v-if="uploading"
      :value="uploadProgress"
      :label="$t('upload.uploading', { percent: Math.round(uploadProgress * 100) })"
    />

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
        :disabled="!file || uploading"
        @click="start"
      >
        {{ $t('upload.start') }}
      </button>
      <button
        v-if="uploading"
        class="button secondary"
        @click="cancelUpload"
      >
        {{ $t('upload.cancel') }}
      </button>
    </div>
  </section>
</template>

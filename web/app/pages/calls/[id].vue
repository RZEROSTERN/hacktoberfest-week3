<script setup lang="ts">
const route = useRoute()
const id = String(route.params.id)
const api = useCalls()
const { call, transcript, loadError, cancel, retry } = useCallStatus(id)

async function remove() {
  if (!window.confirm('Delete this call and its transcript from this computer?')) return
  await api.remove(id)
  await navigateTo('/')
}
</script>

<template>
  <section>
    <p
      v-if="loadError"
      class="error"
      role="alert"
    >
      {{ loadError }}
    </p>
    <p
      v-else-if="!call"
      class="muted"
    >
      Loading…
    </p>

    <template v-else>
      <h1>{{ call.title }}</h1>
      <p class="muted">
        <span v-if="call.language">Language: {{ call.language }}</span>
        <span v-if="call.duration_s"> · {{ formatDuration(call.duration_s) }}</span>
      </p>

      <template v-if="isActive(call.status)">
        <ProgressBar
          :value="call.progress"
          :label="statusLabel(call)"
        />
        <div class="row">
          <button
            class="button secondary"
            @click="cancel"
          >
            Cancel
          </button>
        </div>
      </template>

      <template v-else-if="call.status === 'failed'">
        <p
          class="error"
          role="alert"
        >
          {{ call.error_message }}
        </p>
        <div class="row">
          <button
            v-if="call.audio_available"
            class="button"
            @click="retry"
          >
            Try again
          </button>
          <button
            class="button secondary"
            @click="remove"
          >
            Delete
          </button>
        </div>
      </template>

      <template v-else-if="call.status === 'cancelled'">
        <p>Transcription cancelled. The recording was removed from this computer.</p>
        <div class="row">
          <NuxtLink
            to="/new"
            class="button"
          >
            Upload again
          </NuxtLink>
          <button
            class="button secondary"
            @click="remove"
          >
            Delete
          </button>
        </div>
      </template>

      <template v-else>
        <p class="muted">
          {{ call.audio_available ? 'The audio file is kept on this computer.' : 'The audio file was deleted after transcription.' }}
        </p>
        <TranscriptView :segments="transcript?.segments ?? []" />
        <div class="row">
          <button
            class="button secondary"
            @click="remove"
          >
            Delete call
          </button>
        </div>
      </template>
    </template>
  </section>
</template>

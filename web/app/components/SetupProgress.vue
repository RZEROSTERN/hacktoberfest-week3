<script setup lang="ts">
import type { SetupProgress, SetupStep } from '~/types/api'
import { formatEta, formatProgress, formatSpeed, percent } from '~/utils/bytes'

const props = defineProps<{
  progress: SetupProgress
  /** The recommended model, offered when the chosen one fails its check. */
  recommended: { model: string, title: string } | null
  pausing: boolean
}>()

defineEmits<{
  pause: []
  resume: []
  later: []
  recommended: []
  choose: []
  done: []
}>()

const MARKS = { pending: '○', running: '●', done: '✓', failed: '✕' }

function hasBar(step: SetupStep) {
  return (step.id === 'llm' || step.id === 'whisper') && step.state === 'running' && step.total > 0
}

function barText(step: SetupStep) {
  return [
    `${percent(step.completed, step.total)}%`,
    formatProgress(step.completed, step.total),
    formatSpeed(step.speed_bps),
    formatEta(step.eta_s),
  ].filter(Boolean).join(' · ')
}

const overallText = computed(() => `${Math.round(props.progress.overall.fraction * 100)}% of the setup`)
const state = computed(() => props.progress.state)
const offerRecommended = computed(
  () => props.recommended !== null && props.progress.llm_model !== props.recommended.model,
)
</script>

<template>
  <section class="setup-progress">
    <h1>Setting up Scopewise</h1>

    <ProgressBar
      :value="progress.overall.fraction"
      :label="overallText"
    />

    <ol class="steps">
      <li
        v-for="step in progress.steps"
        :key="step.id"
        :class="[step.state, { main: step.id === 'llm' }]"
        :data-step="step.id"
      >
        <span
          class="mark"
          aria-hidden="true"
        >{{ MARKS[step.state] }}</span>
        <div class="grow">
          <div>
            <strong>{{ step.label }}</strong>
            <span
              v-if="step.detail"
              class="muted detail"
            >{{ step.detail }}</span>
          </div>
          <template v-if="hasBar(step)">
            <ProgressBar
              :value="step.completed / step.total"
              :label="barText(step)"
            />
          </template>
        </div>
      </li>
    </ol>

    <p
      v-if="state === 'interrupted'"
      role="status"
    >
      The download was interrupted when Scopewise closed. Do you want to continue it? It picks up where it stopped.
    </p>
    <p
      v-else-if="state === 'paused'"
      role="status"
    >
      Paused. Nothing is downloading.
    </p>
    <p
      v-else-if="state === 'failed' || state === 'compat_failed'"
      class="error"
      role="alert"
    >
      {{ progress.error_message }}
    </p>
    <p
      v-else-if="state === 'done'"
      role="status"
    >
      Everything is ready. Your calls stay on this computer.
    </p>

    <div class="row">
      <button
        v-if="state === 'running'"
        class="button secondary"
        :disabled="pausing"
        @click="$emit('pause')"
      >
        {{ pausing ? 'Pausing…' : 'Pause' }}
      </button>
      <button
        v-if="state === 'paused' || state === 'interrupted'"
        class="button"
        @click="$emit('resume')"
      >
        Resume
      </button>
      <template v-if="state === 'failed'">
        <button
          class="button"
          @click="$emit('resume')"
        >
          Try again
        </button>
        <button
          class="button secondary"
          @click="$emit('choose')"
        >
          Choose another model
        </button>
      </template>
      <template v-if="state === 'compat_failed'">
        <button
          v-if="offerRecommended && recommended"
          class="button"
          @click="$emit('recommended')"
        >
          Use the recommended model ({{ recommended.title }})
        </button>
        <button
          class="button secondary"
          @click="$emit('choose')"
        >
          Choose another model
        </button>
      </template>
      <button
        v-if="state === 'paused' || state === 'interrupted' || state === 'failed'"
        class="button secondary"
        @click="$emit('later')"
      >
        Not now
      </button>
      <button
        v-if="state === 'done'"
        class="button"
        @click="$emit('done')"
      >
        Start using Scopewise
      </button>
    </div>
  </section>
</template>

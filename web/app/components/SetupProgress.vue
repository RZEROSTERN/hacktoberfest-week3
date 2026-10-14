<script setup lang="ts">
import type { SetupProgress, SetupStep } from '~/types/api'
import { percent } from '~/utils/bytes'

const format = useFormat()
const errors = useErrors()

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
    format.progress(step.completed, step.total),
    format.speed(step.speed_bps),
    format.eta(step.eta_s),
  ].filter(Boolean).join(' · ')
}

const overallText = computed(() => format.t('setup.progress.overall', { percent: Math.round(props.progress.overall.fraction * 100) }))
const state = computed(() => props.progress.state)
const offerRecommended = computed(
  () => props.recommended !== null && props.progress.llm_model !== props.recommended.model,
)
</script>

<template>
  <section class="setup-progress">
    <h1>{{ $t('setup.progress.title') }}</h1>

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
            <strong>{{ $t(`setup.steps.${step.id}`) }}</strong>
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
      {{ $t('setup.progress.interrupted') }}
    </p>
    <p
      v-else-if="state === 'paused'"
      role="status"
    >
      {{ $t('setup.progress.paused') }}
    </p>
    <p
      v-else-if="state === 'failed' || state === 'compat_failed'"
      class="error"
      role="alert"
    >
      {{ errors.job(progress.error_code, progress.error_message) }}
    </p>
    <p
      v-else-if="state === 'done'"
      role="status"
    >
      {{ $t('setup.progress.ready') }}
    </p>

    <div class="row">
      <button
        v-if="state === 'running'"
        class="button secondary"
        :disabled="pausing"
        @click="$emit('pause')"
      >
        {{ pausing ? $t('common.pausing') : $t('common.pause') }}
      </button>
      <button
        v-if="state === 'paused' || state === 'interrupted'"
        class="button"
        @click="$emit('resume')"
      >
        {{ $t('common.resume') }}
      </button>
      <template v-if="state === 'failed'">
        <button
          class="button"
          @click="$emit('resume')"
        >
          {{ $t('common.tryAgain') }}
        </button>
        <button
          class="button secondary"
          @click="$emit('choose')"
        >
          {{ $t('setup.progress.choose') }}
        </button>
      </template>
      <template v-if="state === 'compat_failed'">
        <button
          v-if="offerRecommended && recommended"
          class="button"
          @click="$emit('recommended')"
        >
          {{ $t('setup.progress.useRecommended', { model: recommended.title }) }}
        </button>
        <button
          class="button secondary"
          @click="$emit('choose')"
        >
          {{ $t('setup.progress.choose') }}
        </button>
      </template>
      <button
        v-if="state === 'paused' || state === 'interrupted' || state === 'failed'"
        class="button secondary"
        @click="$emit('later')"
      >
        {{ $t('common.notNow') }}
      </button>
      <button
        v-if="state === 'done'"
        class="button"
        @click="$emit('done')"
      >
        {{ $t('setup.progress.start') }}
      </button>
    </div>
  </section>
</template>

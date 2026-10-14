<script setup lang="ts">
import type { TranscriptSegment } from '~/types/api'

defineProps<{
  segments: TranscriptSegment[]
  /** Segment to highlight, e.g. after the user clicks a source link. */
  highlightId?: number | null
}>()
</script>

<template>
  <p v-if="segments.length === 0">
    {{ $t('transcript.empty') }}
  </p>
  <ol
    v-else
    class="transcript"
  >
    <li
      v-for="segment in segments"
      :id="`segment-${segment.id}`"
      :key="segment.id"
      :class="{ highlight: segment.id === highlightId }"
    >
      <time class="stamp">{{ formatTimestamp(segment.start) }}</time>
      <span dir="auto">{{ segment.text }}</span>
    </li>
  </ol>
</template>

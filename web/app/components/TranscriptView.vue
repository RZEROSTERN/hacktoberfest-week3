<script setup lang="ts">
import type { TranscriptSegment } from '~/types/api'

defineProps<{ segments: TranscriptSegment[] }>()
</script>

<template>
  <p v-if="segments.length === 0">
    No speech was detected in this recording.
  </p>
  <ol
    v-else
    class="transcript"
  >
    <li
      v-for="segment in segments"
      :id="`segment-${segment.id}`"
      :key="segment.id"
    >
      <time class="stamp">{{ formatTimestamp(segment.start) }}</time>
      <span>{{ segment.text }}</span>
    </li>
  </ol>
</template>

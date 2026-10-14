<script setup lang="ts">
import type { Source } from '~/types/api'

defineProps<{ sources: Source[] }>()
defineEmits<{ show: [segmentId: number] }>()

const selected = ref<number | null>(null)

function toggle(segmentId: number) {
  selected.value = selected.value === segmentId ? null : segmentId
}
</script>

<template>
  <span class="chips">
    <button
      v-for="source in sources"
      :key="source.segment_id"
      type="button"
      class="chip"
      :aria-expanded="selected === source.segment_id"
      :title="$t('source.at', { time: formatTimestamp(source.start) })"
      @click="toggle(source.segment_id)"
    >
      <span
        class="play"
        aria-hidden="true"
      >▶</span> <bdi>{{ formatTimestamp(source.start) }}</bdi>
    </button>
    <template
      v-for="source in sources"
      :key="`quote-${source.segment_id}`"
    >
      <blockquote
        v-if="selected === source.segment_id"
        class="quote"
      >
        <span class="stamp">{{ formatTimestamp(source.start) }}</span>
        <q dir="auto">{{ source.text }}</q>
        <button
          type="button"
          class="link"
          @click="$emit('show', source.segment_id)"
        >
          {{ $t('source.show') }}
        </button>
      </blockquote>
    </template>
  </span>
</template>

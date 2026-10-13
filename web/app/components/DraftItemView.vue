<script setup lang="ts">
import type { DraftItem } from '~/types/api'

defineProps<{ item: DraftItem }>()
defineEmits<{ show: [segmentId: number] }>()

const selected = ref<number | null>(null)

function toggle(segmentId: number) {
  selected.value = selected.value === segmentId ? null : segmentId
}
</script>

<template>
  <li class="draft-item">
    <span>{{ item.text }}</span>
    <span
      v-if="item.assumption"
      class="badge"
      title="This was not said in the call. Check it before sending."
    >Assumption</span>
    <button
      v-for="source in item.sources"
      :key="source.segment_id"
      type="button"
      class="chip"
      :aria-expanded="selected === source.segment_id"
      :title="`Source in the call at ${formatTimestamp(source.start)}`"
      @click="toggle(source.segment_id)"
    >
      ▶ {{ formatTimestamp(source.start) }}
    </button>
    <template
      v-for="source in item.sources"
      :key="`quote-${source.segment_id}`"
    >
      <blockquote
        v-if="selected === source.segment_id"
        class="quote"
      >
        <span class="stamp">{{ formatTimestamp(source.start) }}</span>
        “{{ source.text }}”
        <button
          type="button"
          class="link"
          @click="$emit('show', source.segment_id)"
        >
          Show in transcript
        </button>
      </blockquote>
    </template>
  </li>
</template>

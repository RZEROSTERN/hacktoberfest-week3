<script setup lang="ts">
import type { DraftItem } from '~/types/api'

defineProps<{ item: DraftItem }>()
defineEmits<{ show: [segmentId: number] }>()
</script>

<template>
  <li class="draft-item">
    <span>{{ item.text }}</span>
    <span
      v-if="item.assumption"
      class="badge"
      title="This was not said in the call. Check it before sending."
    >Assumption</span>
    <SourceChips
      :sources="item.sources"
      @show="$emit('show', $event)"
    />
  </li>
</template>

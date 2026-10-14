<script setup lang="ts">
import type { DraftItem } from '~/types/api'

defineProps<{ item: DraftItem }>()
defineEmits<{ show: [segmentId: number] }>()
</script>

<template>
  <li class="draft-item">
    <span dir="auto">{{ item.text }}</span>
    <span
      v-if="item.assumption"
      class="badge"
      :title="$t('draft.assumptionTitle')"
    >{{ $t('editor.assumption') }}</span>
    <SourceChips
      :sources="item.sources"
      @show="$emit('show', $event)"
    />
  </li>
</template>

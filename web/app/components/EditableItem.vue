<script setup lang="ts">
import type { DraftItem } from '~/types/api'

const item = defineModel<DraftItem>({ required: true })

defineProps<{
  /** Whether the user can flag the item as an assumption (not for the client's budget note). */
  flaggable?: boolean
}>()

defineEmits<{ remove: [], show: [segmentId: number] }>()
</script>

<template>
  <li class="editable-item">
    <div class="row">
      <input
        v-model="item.text"
        type="text"
        class="grow"
        dir="auto"
        :aria-label="$t('editor.itemText')"
      >
      <button
        type="button"
        class="icon"
        :aria-label="$t('editor.removeItem')"
        :title="$t('editor.removeItem')"
        @click="$emit('remove')"
      >
        ✕
      </button>
    </div>
    <div class="row small">
      <label v-if="flaggable">
        <input
          v-model="item.assumption"
          type="checkbox"
          :disabled="item.sources.length === 0"
        >
        {{ item.sources.length === 0 ? $t('editor.assumptionNoSource') : $t('editor.assumption') }}
      </label>
      <SourceChips
        :sources="item.sources"
        @show="$emit('show', $event)"
      />
    </div>
  </li>
</template>

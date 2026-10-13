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
        aria-label="Item text"
      >
      <button
        type="button"
        class="icon"
        aria-label="Remove item"
        title="Remove item"
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
        Assumption{{ item.sources.length === 0 ? ' (no source in the call)' : '' }}
      </label>
      <SourceChips
        :sources="item.sources"
        @show="$emit('show', $event)"
      />
    </div>
  </li>
</template>

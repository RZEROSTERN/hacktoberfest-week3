<script setup lang="ts">
const props = defineProps<{
  /** 0 to 1 */
  value: number
  label: string
}>()

const percent = computed(() => Math.round(Math.min(1, Math.max(0, props.value)) * 100))
</script>

<template>
  <div class="progress">
    <progress
      :value="percent"
      max="100"
      :aria-label="label"
    />
    <span>{{ label }}</span>
  </div>
</template>

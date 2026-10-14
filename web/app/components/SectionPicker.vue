<script setup lang="ts">
import { moveChoice, type SectionChoice } from '~/utils/sections'

const choices = defineModel<SectionChoice[]>({ required: true })

function toggle(index: number) {
  choices.value = choices.value.map((c, i) => (i === index ? { ...c, enabled: !c.enabled } : c))
}
</script>

<template>
  <fieldset class="sections">
    <legend>{{ $t('sections.legend') }}</legend>
    <p class="muted">
      {{ $t('sections.help') }}
    </p>
    <ol>
      <li
        v-for="(choice, index) in choices"
        :key="choice.id"
      >
        <label>
          <input
            type="checkbox"
            :checked="choice.enabled"
            @change="toggle(index)"
          >
          {{ $t(`sections.${choice.id}`) }}
        </label>
        <span class="move">
          <button
            type="button"
            class="icon"
            :disabled="index === 0"
            :aria-label="$t('sections.moveUp', { section: $t(`sections.${choice.id}`) })"
            @click="choices = moveChoice(choices, index, -1)"
          >↑</button>
          <button
            type="button"
            class="icon"
            :disabled="index === choices.length - 1"
            :aria-label="$t('sections.moveDown', { section: $t(`sections.${choice.id}`) })"
            @click="choices = moveChoice(choices, index, 1)"
          >↓</button>
        </span>
      </li>
    </ol>
  </fieldset>
</template>

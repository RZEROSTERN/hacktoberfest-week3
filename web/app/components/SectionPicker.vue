<script setup lang="ts">
import { moveChoice, sectionLabel, type SectionChoice } from '~/utils/sections'

const choices = defineModel<SectionChoice[]>({ required: true })

function toggle(index: number) {
  choices.value = choices.value.map((c, i) => (i === index ? { ...c, enabled: !c.enabled } : c))
}
</script>

<template>
  <fieldset class="sections">
    <legend>Proposal sections</legend>
    <p class="muted">
      Choose the sections your proposals include and their order. The investment section always comes after the scope.
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
          {{ sectionLabel(choice.id) }}
        </label>
        <span class="move">
          <button
            type="button"
            class="icon"
            :disabled="index === 0"
            :aria-label="`Move ${sectionLabel(choice.id)} up`"
            @click="choices = moveChoice(choices, index, -1)"
          >↑</button>
          <button
            type="button"
            class="icon"
            :disabled="index === choices.length - 1"
            :aria-label="`Move ${sectionLabel(choice.id)} down`"
            @click="choices = moveChoice(choices, index, 1)"
          >↓</button>
        </span>
      </li>
    </ol>
  </fieldset>
</template>

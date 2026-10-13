<script setup lang="ts">
import type { LlmChoice, Recommended } from '~/types/api'
import { formatBytes, formatMemory } from '~/utils/bytes'
import { CUSTOM, ramWarning, type ModelSelection } from '~/utils/setup'

const selection = defineModel<ModelSelection>({ required: true })

const props = defineProps<{ data: Recommended }>()

const best = computed(() => props.data.llm.filter(c => c.recommended))
const others = computed(() => props.data.llm.filter(c => !c.recommended))

function warning(choice: LlmChoice) {
  return ramWarning(choice, props.data.system.total_ram_bytes)
}
</script>

<template>
  <fieldset class="picker">
    <legend>Language model</legend>
    <p class="muted">
      The language model reads your call notes and writes the draft. It runs on this computer.
    </p>

    <label
      v-for="choice in best"
      :key="choice.model"
      class="choice"
    >
      <input
        v-model="selection.choice"
        type="radio"
        name="model"
        :value="choice.model"
      >
      <span>
        <span class="title-row">
          <strong>{{ choice.title }}</strong>
          <span class="badge good">Recommended</span>
          <span
            v-if="choice.not_recommended_for_this_computer"
            class="badge warn"
          >Not recommended for this computer</span>
          <span
            v-if="choice.installed"
            class="badge"
          >Already on this computer</span>
        </span>
        <span class="muted facts">
          {{ formatBytes(choice.size_bytes) }} download · about {{ choice.ram_gb }} GB of memory · {{ choice.license }}
        </span>
        <span class="muted">{{ choice.note }}</span>
        <span
          v-if="warning(choice)"
          class="warn-text"
        >{{ warning(choice) }}</span>
      </span>
    </label>

    <details>
      <summary>Other models we tested</summary>
      <label
        v-for="choice in others"
        :key="choice.model"
        class="choice"
      >
        <input
          v-model="selection.choice"
          type="radio"
          name="model"
          :value="choice.model"
        >
        <span>
          <span class="title-row">
            <strong>{{ choice.title }}</strong>
            <span
              v-if="choice.not_recommended_for_this_computer"
              class="badge warn"
            >Not recommended for this computer</span>
            <span
              v-if="choice.installed"
              class="badge"
            >Already on this computer</span>
          </span>
          <span class="muted facts">
            {{ formatBytes(choice.size_bytes) }} download · about {{ choice.ram_gb }} GB of memory · {{ choice.license }}
          </span>
          <span class="muted">{{ choice.note }}</span>
          <span
            v-if="warning(choice)"
            class="warn-text"
          >{{ warning(choice) }}</span>
        </span>
      </label>
    </details>

    <details :open="selection.choice === CUSTOM">
      <summary>Advanced: use another model from Ollama</summary>
      <label class="choice">
        <input
          v-model="selection.choice"
          type="radio"
          name="model"
          :value="CUSTOM"
        >
        <span>
          <strong>Use this model name</strong>
          <input
            v-model="selection.custom"
            type="text"
            class="wide"
            placeholder="name:tag, for example llama3.2:3b"
            aria-label="Ollama model name and tag"
            @focus="selection.choice = CUSTOM"
          >
          <span class="muted">
            Any model name and tag from the
            <a
              :href="data.library_url"
              target="_blank"
              rel="noopener"
            >Ollama library</a>.
            Models we have not tested may give lower quality. It is tried on a short sample call before you can use it.
            Cloud models are not allowed: your calls never leave this computer.
          </span>
        </span>
      </label>
    </details>
    <p class="muted">
      This computer has {{ formatMemory(data.system.total_ram_bytes) }} of memory.
    </p>
  </fieldset>
</template>

<script setup lang="ts">
import type { LlmChoice, Recommended } from '~/types/api'
import { CUSTOM, ramWarning, type ModelSelection } from '~/utils/setup'

const selection = defineModel<ModelSelection>({ required: true })

const props = defineProps<{ data: Recommended }>()
const format = useFormat()

const best = computed(() => props.data.llm.filter(c => c.recommended))
const others = computed(() => props.data.llm.filter(c => !c.recommended))

function warning(choice: LlmChoice) {
  const values = ramWarning(choice, props.data.system.total_ram_bytes)
  return values ? format.t('picker.ramWarning', { need: format.gigabytes(values.need), have: format.gigabytes(values.have) }) : null
}

function facts(choice: LlmChoice) {
  return format.t('picker.facts', {
    size: format.bytes(choice.size_bytes),
    memory: format.gigabytes(choice.ram_gb),
    license: choice.license,
  })
}
</script>

<template>
  <fieldset class="picker">
    <legend>{{ $t('picker.legend') }}</legend>
    <p class="muted">
      {{ $t('picker.intro') }}
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
          <span class="badge good">{{ $t('picker.recommended') }}</span>
          <span
            v-if="choice.not_recommended_for_this_computer"
            class="badge warn"
          >{{ $t('picker.notRecommended') }}</span>
          <span
            v-if="choice.installed"
            class="badge"
          >{{ $t('picker.installed') }}</span>
        </span>
        <span class="muted facts">{{ facts(choice) }}</span>
        <span class="muted">{{ format.modelNote(choice.model, choice.note) }}</span>
        <span
          v-if="warning(choice)"
          class="warn-text"
        >{{ warning(choice) }}</span>
      </span>
    </label>

    <details>
      <summary>{{ $t('picker.others') }}</summary>
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
            >{{ $t('picker.notRecommended') }}</span>
            <span
              v-if="choice.installed"
              class="badge"
            >{{ $t('picker.installed') }}</span>
          </span>
          <span class="muted facts">{{ facts(choice) }}</span>
          <span class="muted">{{ format.modelNote(choice.model, choice.note) }}</span>
          <span
            v-if="warning(choice)"
            class="warn-text"
          >{{ warning(choice) }}</span>
        </span>
      </label>
    </details>

    <details :open="selection.choice === CUSTOM">
      <summary>{{ $t('picker.advanced') }}</summary>
      <label class="choice">
        <input
          v-model="selection.choice"
          type="radio"
          name="model"
          :value="CUSTOM"
        >
        <span>
          <strong>{{ $t('picker.useName') }}</strong>
          <input
            v-model="selection.custom"
            type="text"
            class="wide"
            dir="ltr"
            :placeholder="$t('picker.placeholder')"
            :aria-label="$t('picker.nameLabel')"
            @focus="selection.choice = CUSTOM"
          >
          <i18n-t
            keypath="picker.advancedNote"
            tag="span"
            class="muted"
          >
            <template #library>
              <a
                :href="data.library_url"
                target="_blank"
                rel="noopener"
              >{{ $t('picker.library') }}</a>
            </template>
          </i18n-t>
        </span>
      </label>
    </details>
    <p class="muted">
      {{ $t('picker.memory', { memory: format.memory(data.system.total_ram_bytes) }) }}
    </p>
  </fieldset>
</template>

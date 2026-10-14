<script setup lang="ts">
import type { ProposalSection } from '~/types/api'
import { isItemSection, isTextOnly, newItem } from '~/utils/editor'

const sections = defineModel<ProposalSection[]>({ required: true })

defineEmits<{ show: [segmentId: number] }>()

function remove<T>(list: T[], index: number) {
  list.splice(index, 1)
}
</script>

<template>
  <div class="proposal editor">
    <section
      v-for="section in sections"
      :key="section.id"
      :data-section="section.id"
    >
      <h3 dir="auto">
        {{ section.title }}
      </h3>

      <textarea
        v-if="isTextOnly(section.id)"
        v-model="section.text"
        rows="4"
        class="wide"
        dir="auto"
        :aria-label="section.title"
      />

      <template v-else-if="isItemSection(section.id)">
        <ul class="plain">
          <EditableItem
            v-for="(item, index) in section.items"
            :key="index"
            v-model="section.items[index]!"
            flaggable
            @remove="remove(section.items, index)"
            @show="$emit('show', $event)"
          />
        </ul>
        <button
          type="button"
          class="button secondary"
          @click="section.items.push(newItem())"
        >
          {{ $t('editor.addItem') }}
        </button>
      </template>

      <template v-else-if="section.id === 'open_questions'">
        <ul class="plain">
          <li
            v-for="(_, index) in section.lines"
            :key="index"
            class="row"
          >
            <input
              v-model="section.lines[index]"
              type="text"
              class="grow"
              dir="auto"
              :aria-label="$t('editor.question')"
            >
            <button
              type="button"
              class="icon"
              :aria-label="$t('editor.removeQuestion')"
              @click="remove(section.lines, index)"
            >
              ✕
            </button>
          </li>
        </ul>
        <button
          type="button"
          class="button secondary"
          @click="section.lines.push('')"
        >
          {{ $t('editor.addQuestion') }}
        </button>
      </template>

      <template v-else>
        <!-- investment: the price sentence, your rates, and the client's budget note -->
        <textarea
          v-model="section.text"
          rows="2"
          class="wide"
          dir="auto"
          :aria-label="$t('editor.priceNote')"
        />
        <p class="muted">
          {{ $t('editor.rates') }}
        </p>
        <ul class="plain">
          <li
            v-for="(_, index) in section.lines"
            :key="index"
            class="row"
          >
            <input
              v-model="section.lines[index]"
              type="text"
              class="grow"
              dir="auto"
              :aria-label="$t('editor.rate')"
            >
            <button
              type="button"
              class="icon"
              :aria-label="$t('editor.removeRate')"
              @click="remove(section.lines, index)"
            >
              ✕
            </button>
          </li>
        </ul>
        <button
          type="button"
          class="button secondary"
          @click="section.lines.push('')"
        >
          {{ $t('editor.addRate') }}
        </button>
        <template v-if="section.items.length">
          <p
            class="muted"
            dir="auto"
          >
            {{ section.items_label }}
          </p>
          <ul class="plain">
            <EditableItem
              v-for="(item, index) in section.items"
              :key="index"
              v-model="section.items[index]!"
              @remove="remove(section.items, index)"
              @show="$emit('show', $event)"
            />
          </ul>
        </template>
      </template>
    </section>
  </div>
</template>

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
      <h3>{{ section.title }}</h3>

      <textarea
        v-if="isTextOnly(section.id)"
        v-model="section.text"
        rows="4"
        class="wide"
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
          Add item
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
              aria-label="Question"
            >
            <button
              type="button"
              class="icon"
              aria-label="Remove question"
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
          Add question
        </button>
      </template>

      <template v-else>
        <!-- investment: the price sentence, your rates, and the client's budget note -->
        <textarea
          v-model="section.text"
          rows="2"
          class="wide"
          aria-label="Price note"
        />
        <p class="muted">
          Rates (written as you want them to appear)
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
              aria-label="Rate"
            >
            <button
              type="button"
              class="icon"
              aria-label="Remove rate"
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
          Add rate
        </button>
        <template v-if="section.items.length">
          <p class="muted">
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

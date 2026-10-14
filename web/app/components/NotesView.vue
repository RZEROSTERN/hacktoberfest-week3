<script setup lang="ts">
import type { DraftNotes } from '~/types/api'

defineProps<{ notes: DraftNotes }>()
defineEmits<{ show: [segmentId: number] }>()

const GROUPS = [
  'client_context',
  'problem',
  'goals',
  'requirements',
  'constraints',
  'budget',
  'deadlines',
  'next_steps',
  'risks',
]
</script>

<template>
  <div class="proposal">
    <p v-if="notes.client">
      <strong>{{ $t('notes.client') }}</strong> <bdi>{{ notes.client }}</bdi>
    </p>
    <template
      v-for="group in GROUPS"
      :key="group"
    >
      <section v-if="notes.groups[group]?.length">
        <h3>{{ $t(`notes.groups.${group}`) }}</h3>
        <ul>
          <DraftItemView
            v-for="(item, index) in notes.groups[group]"
            :key="index"
            :item="item"
            @show="$emit('show', $event)"
          />
        </ul>
      </section>
    </template>
    <section v-if="notes.open_questions.length">
      <h3>{{ $t('notes.openQuestions') }}</h3>
      <ul>
        <li
          v-for="question in notes.open_questions"
          :key="question"
          dir="auto"
        >
          {{ question }}
        </li>
      </ul>
    </section>
  </div>
</template>

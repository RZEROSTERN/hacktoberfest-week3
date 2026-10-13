<script setup lang="ts">
import type { DraftNotes } from '~/types/api'

defineProps<{ notes: DraftNotes }>()
defineEmits<{ show: [segmentId: number] }>()

const LABELS: Record<string, string> = {
  client_context: 'About the client',
  problem: 'Problem',
  goals: 'Goals',
  requirements: 'Requirements',
  constraints: 'Constraints',
  budget: 'Budget mentioned',
  deadlines: 'Deadlines mentioned',
  next_steps: 'Next steps',
  risks: 'Risks',
}
</script>

<template>
  <div class="proposal">
    <p v-if="notes.client">
      <strong>Client:</strong> {{ notes.client }}
    </p>
    <template
      v-for="(label, group) in LABELS"
      :key="group"
    >
      <section v-if="notes.groups[group]?.length">
        <h3>{{ label }}</h3>
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
      <h3>Questions the call left open</h3>
      <ul>
        <li
          v-for="question in notes.open_questions"
          :key="question"
        >
          {{ question }}
        </li>
      </ul>
    </section>
  </div>
</template>

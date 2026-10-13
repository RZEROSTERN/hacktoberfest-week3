<script setup lang="ts">
import type { ProposalSection } from '~/types/api'

defineProps<{ sections: ProposalSection[] }>()
defineEmits<{ show: [segmentId: number] }>()

const isEmpty = (s: ProposalSection) => !s.text.trim() && s.lines.length === 0 && s.items.length === 0
</script>

<template>
  <div class="proposal">
    <section
      v-for="section in sections"
      :key="section.id"
      :data-section="section.id"
    >
      <h3>{{ section.title }}</h3>
      <p
        v-if="isEmpty(section)"
        class="muted"
      >
        Nothing was identified for this section.
      </p>
      <p
        v-if="section.text"
        class="prewrap"
      >
        {{ section.text }}
      </p>
      <ul v-if="section.lines.length">
        <li
          v-for="line in section.lines"
          :key="line"
        >
          {{ line }}
        </li>
      </ul>
      <template v-if="section.items.length">
        <p
          v-if="section.items_label"
          class="muted"
        >
          {{ section.items_label }}
        </p>
        <ul>
          <DraftItemView
            v-for="(item, index) in section.items"
            :key="index"
            :item="item"
            @show="$emit('show', $event)"
          />
        </ul>
      </template>
    </section>
  </div>
</template>

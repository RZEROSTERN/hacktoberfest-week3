<script setup lang="ts">
import raw from '../../../THIRD_PARTY_NOTICES.md?raw'
import { parseNotices } from '~/utils/notices'

const sections = parseNotices(raw)
</script>

<template>
  <section class="notices">
    <h1>Third-party notices</h1>
    <p class="muted">
      Scopewise is made of open-source parts that run on your computer. Here is what is inside and under which license.
    </p>
    <section
      v-for="section in sections"
      :key="section.title"
    >
      <h2>{{ section.title }}</h2>
      <p
        v-for="(paragraph, i) in section.paragraphs"
        :key="i"
        class="paragraph"
      >
        {{ paragraph }}
      </p>
    </section>
  </section>
</template>

<style scoped>
.paragraph {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>

<script setup lang="ts">
import type { LocaleCode } from '~/i18n/locales'

const { code, locales, setLocale } = useLocale()

function onChange(event: Event) {
  void setLocale((event.target as HTMLSelectElement).value as LocaleCode)
}
</script>

<template>
  <select
    class="language-switcher"
    :value="code"
    :aria-label="$t('language.label')"
    @change="onChange"
  >
    <option
      v-for="locale in locales"
      :key="locale.code"
      :value="locale.code"
      :lang="locale.htmlLang"
    >
      {{ locale.name }}
    </option>
  </select>
</template>

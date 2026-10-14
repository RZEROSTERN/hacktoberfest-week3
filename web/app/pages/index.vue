<script setup lang="ts">
import type { Call } from '~/types/api'

const api = useCalls()
const profileApi = useProfile()
const format = useFormat()
const hasProfile = ref(true) // assume yes until we know, to avoid a flash of the notice
const calls = ref<Call[]>([])
const loading = ref(true)
const unreachable = ref(false)

onMounted(async () => {
  try {
    calls.value = await api.list()
    hasProfile.value = (await profileApi.load()) !== null
  } catch {
    unreachable.value = true
  } finally {
    loading.value = false
  }
})

function facts(call: Call) {
  return [format.language(call.language), format.duration(call.duration_s)].filter(Boolean).join(' · ')
}
</script>

<template>
  <section>
    <h1>{{ $t('home.title') }}</h1>
    <p class="muted">
      {{ $t('home.intro') }}
    </p>
    <aside
      v-if="!hasProfile"
      class="notice"
      role="note"
    >
      <strong>{{ $t('profileNotice.title') }}</strong>
      {{ $t('home.profileNotice') }}
      <NuxtLink to="/profile">
        {{ $t('profileNotice.link') }}
      </NuxtLink>
    </aside>
    <NuxtLink
      to="/new"
      class="button"
    >
      {{ $t('home.newProposal') }}
    </NuxtLink>

    <p
      v-if="unreachable"
      class="error"
    >
      {{ $t('errors.engineUnreachable') }}
    </p>
    <p
      v-else-if="loading"
      class="muted"
    >
      {{ $t('common.loading') }}
    </p>
    <p
      v-else-if="calls.length === 0"
      class="muted"
    >
      {{ $t('home.noCalls') }}
    </p>
    <ul
      v-else
      class="calls"
    >
      <li
        v-for="call in calls"
        :key="call.id"
      >
        <NuxtLink
          :to="`/calls/${call.id}`"
          dir="auto"
        >
          {{ call.title }}
        </NuxtLink>
        <span class="muted">{{ format.callStatus(call) }}</span>
        <span
          v-if="call.language || call.duration_s"
          class="muted facts"
        >{{ facts(call) }}</span>
      </li>
    </ul>
  </section>
</template>

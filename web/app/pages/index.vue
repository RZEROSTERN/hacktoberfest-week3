<script setup lang="ts">
import type { Call } from '~/types/api'

const api = useCalls()
const profileApi = useProfile()
const hasProfile = ref(true) // assume yes until we know, to avoid a flash of the notice
const calls = ref<Call[]>([])
const loading = ref(true)
const loadError = ref<string | null>(null)

onMounted(async () => {
  try {
    calls.value = await api.list()
    hasProfile.value = (await profileApi.load()) !== null
  } catch {
    loadError.value = 'Could not reach the local engine. Is the app still running?'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section>
    <h1>Your calls</h1>
    <p class="muted">
      Turn a recorded client call into a draft proposal. Everything stays on this computer.
    </p>
    <aside
      v-if="!hasProfile"
      class="notice"
      role="note"
    >
      <strong>Set up your profile first.</strong>
      Your services, rates and payment terms go into every proposal.
      <NuxtLink to="/profile">
        Set up my profile
      </NuxtLink>
    </aside>
    <NuxtLink
      to="/new"
      class="button"
    >
      New proposal
    </NuxtLink>

    <p
      v-if="loadError"
      class="error"
    >
      {{ loadError }}
    </p>
    <p
      v-else-if="loading"
      class="muted"
    >
      Loading…
    </p>
    <p
      v-else-if="calls.length === 0"
      class="muted"
    >
      No calls yet. Upload your first recording to get started.
    </p>
    <ul
      v-else
      class="calls"
    >
      <li
        v-for="call in calls"
        :key="call.id"
      >
        <NuxtLink :to="`/calls/${call.id}`">
          {{ call.title }}
        </NuxtLink>
        <span class="muted">{{ statusLabel(call) }}</span>
      </li>
    </ul>
  </section>
</template>

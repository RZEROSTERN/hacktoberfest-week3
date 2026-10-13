<script setup lang="ts">
const { apiFetch } = useApi()

const status = ref<'checking' | 'ok' | 'down'>('checking')

onMounted(async () => {
  try {
    await apiFetch('/health')
    status.value = 'ok'
  } catch {
    status.value = 'down'
  }
})
</script>

<template>
  <main>
    <h1>Scopewise</h1>
    <p v-if="status === 'checking'">
      Checking the local engine…
    </p>
    <p v-else-if="status === 'ok'">
      Local engine is running.
    </p>
    <p v-else>
      The local engine is not reachable.
    </p>
  </main>
</template>

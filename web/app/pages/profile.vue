<script setup lang="ts">
import { apiErrorMessage } from '~/utils/format'
import { emptyProfileForm, formFromProfile, profileFromForm } from '~/utils/profileForm'

const profileApi = useProfile()

const form = ref(emptyProfileForm())
const loading = ref(true)
const loadError = ref<string | null>(null)
const saving = ref(false)
const saved = ref(false)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    const profile = await profileApi.load()
    if (profile) form.value = formFromProfile(profile)
  } catch {
    loadError.value = 'Could not reach the local engine. Is the app still running?'
  } finally {
    loading.value = false
  }
})

// Editing again clears the "saved" confirmation.
watch(form, () => (saved.value = false), { deep: true })

async function save() {
  saving.value = true
  error.value = null
  try {
    const result = await profileApi.save(profileFromForm(form.value))
    form.value = formFromProfile(result)
    await nextTick()
    saved.value = true
  } catch (e) {
    error.value = apiErrorMessage(e, 'The profile could not be saved.')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section>
    <h1>Your profile</h1>
    <p class="muted">
      Used to write your proposals: your services, rates, payment terms, tone and the sections you prefer. It stays on this computer.
    </p>
    <p
      v-if="loadError"
      class="error"
      role="alert"
    >
      {{ loadError }}
    </p>
    <p
      v-else-if="loading"
      class="muted"
    >
      Loading…
    </p>
    <ProfileForm
      v-else
      v-model="form"
      :saving="saving"
      :error="error"
      :saved="saved"
      @submit="save"
    />
  </section>
</template>

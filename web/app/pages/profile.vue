<script setup lang="ts">
import { emptyProfileForm, formFromProfile, profileFromForm } from '~/utils/profileForm'

const profileApi = useProfile()
const errors = useErrors()

const form = ref(emptyProfileForm())
const loading = ref(true)
const unreachable = ref(false)
const saving = ref(false)
const saved = ref(false)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    const profile = await profileApi.load()
    if (profile) form.value = formFromProfile(profile)
  } catch {
    unreachable.value = true
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
    error.value = errors.message(e, 'errors.profileSave')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section>
    <h1>{{ $t('profile.title') }}</h1>
    <p class="muted">
      {{ $t('profile.intro') }}
    </p>
    <p
      v-if="unreachable"
      class="error"
      role="alert"
    >
      {{ $t('errors.engineUnreachable') }}
    </p>
    <p
      v-else-if="loading"
      class="muted"
    >
      {{ $t('common.loading') }}
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

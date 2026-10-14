<script setup lang="ts">
import type { ProfileFormState } from '~/utils/profileForm'

const form = defineModel<ProfileFormState>({ required: true })

defineProps<{
  saving: boolean
  error: string | null
  saved: boolean
}>()

defineEmits<{ submit: [] }>()
</script>

<template>
  <form
    class="form"
    @submit.prevent="$emit('submit')"
  >
    <div class="page-grid">
      <div class="form">
        <label>
          {{ $t('profile.name') }}
          <input
            v-model="form.name"
            type="text"
            required
            autocomplete="organization"
          >
        </label>

        <label>
          {{ $t('profile.services') }} <span class="muted">{{ $t('profile.servicesHint') }}</span>
          <textarea
            v-model="form.servicesText"
            rows="3"
          />
        </label>

        <label>
          {{ $t('profile.hourlyRate') }} <span class="muted">{{ $t('profile.hourlyRateHint') }}</span>
          <input
            v-model="form.hourlyRate"
            type="text"
          >
        </label>

        <label>
          {{ $t('profile.projectRates') }} <span class="muted">{{ $t('profile.projectRatesHint') }}</span>
          <textarea
            v-model="form.projectRatesText"
            rows="3"
          />
        </label>
        <p class="muted">
          {{ $t('profile.ratesNote') }}
        </p>

      </div>

      <div class="form">
        <label>
          {{ $t('profile.paymentTerms') }}
          <textarea
            v-model="form.paymentTerms"
            rows="2"
          />
        </label>

        <label>
          {{ $t('profile.tone') }} <span class="muted">{{ $t('profile.toneHint') }}</span>
          <input
            v-model="form.tone"
            type="text"
          >
        </label>

        <SectionPicker v-model="form.sections" />
      </div>
    </div>

    <p
      v-if="error"
      class="error"
      role="alert"
    >
      {{ error }}
    </p>
    <p
      v-if="saved"
      role="status"
    >
      {{ $t('profile.saved') }}
    </p>

    <div class="row">
      <button
        class="button"
        type="submit"
        :disabled="saving || !form.name.trim()"
      >
        {{ saving ? $t('common.saving') : $t('profile.save') }}
      </button>
    </div>
  </form>
</template>

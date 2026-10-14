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
          Name or business name
          <input
            v-model="form.name"
            type="text"
            required
            autocomplete="organization"
          >
        </label>

        <label>
          Services you offer <span class="muted">(one per line)</span>
          <textarea
            v-model="form.servicesText"
            rows="3"
          />
        </label>

        <label>
          Hourly rate <span class="muted">(any currency, written as you want it to appear, e.g. 650 MXN per hour)</span>
          <input
            v-model="form.hourlyRate"
            type="text"
          >
        </label>

        <label>
          Project rates <span class="muted">(one per line, e.g. Website up to 5 sections: 24,000 MXN)</span>
          <textarea
            v-model="form.projectRatesText"
            rows="3"
          />
        </label>
        <p class="muted">
          Prices in your proposals come only from these rates. A budget the client mentions is shown as a note, never used as the price.
        </p>

      </div>

      <div class="form">
        <label>
          Default payment terms
          <textarea
            v-model="form.paymentTerms"
            rows="2"
          />
        </label>

        <label>
          Tone <span class="muted">(e.g. professional and friendly)</span>
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
      Profile saved.
    </p>

    <div class="row">
      <button
        class="button"
        type="submit"
        :disabled="saving || !form.name.trim()"
      >
        {{ saving ? 'Saving…' : 'Save profile' }}
      </button>
    </div>
  </form>
</template>

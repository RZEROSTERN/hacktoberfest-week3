<script setup lang="ts">
import type { ProposalSection } from '~/types/api'

const route = useRoute()
const id = String(route.params.id)
const api = useCalls()
const profileApi = useProfile()
const { call, transcript, loadError, cancel, retry } = useCallStatus(id)
const {
  draft,
  error: draftError,
  start: startDraft,
  cancel: cancelDraft,
  saveEdits,
  download,
} = useDraftStatus(id)

const language = ref('') // '' = the language of the call
const profileKnown = ref(false)
const hasProfile = ref(false)
const transcriptOpen = ref(false)
const highlightId = ref<number | null>(null)
const cancelling = ref(false)
const editing = ref(false)
const editSections = ref<ProposalSection[]>([])
const saving = ref(false)
const justSaved = ref(false)

onMounted(async () => {
  try {
    hasProfile.value = (await profileApi.load()) !== null
  } catch {
    hasProfile.value = false
  } finally {
    profileKnown.value = true
  }
})

const canStart = computed(() => !draft.value || !isDraftActive(draft.value.status))

// Stopping can take a moment (the model may still be loading), so say so right away.
watch(() => draft.value?.status, (status) => {
  if (!status || !isDraftActive(status)) cancelling.value = false
})

async function onCancelDraft() {
  cancelling.value = true
  await cancelDraft()
}

async function remove() {
  if (!window.confirm('Delete this call and its transcript from this computer?')) return
  await api.remove(id)
  await navigateTo('/')
}

async function draftAgain() {
  if (draft.value?.status === 'done' && !window.confirm('Write a new draft? It replaces the current one, including any changes you made.')) return
  await startDraft(language.value || null)
}

const dirty = computed(() => editing.value && !!draft.value?.proposal && isDirty(draft.value.proposal.sections, editSections.value))

function startEditing() {
  if (!draft.value?.proposal) return
  editSections.value = cloneSections(draft.value.proposal.sections)
  justSaved.value = false
  editing.value = true
}

function discardEditing() {
  if (dirty.value && !window.confirm('Discard your changes?')) return
  editing.value = false
}

async function saveChanges() {
  saving.value = true
  try {
    if (await saveEdits(toPayload(editSections.value))) {
      editing.value = false
      justSaved.value = true
    }
  } finally {
    saving.value = false
  }
}

onBeforeRouteLeave(() => !dirty.value || window.confirm('You have unsaved changes. Leave without saving?'))

/** Open the transcript, scroll to the cited segment and highlight it for a moment. */
async function showInTranscript(segmentId: number) {
  transcriptOpen.value = true
  highlightId.value = segmentId
  await nextTick()
  document.getElementById(`segment-${segmentId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  setTimeout(() => {
    if (highlightId.value === segmentId) highlightId.value = null
  }, 4000)
}
</script>

<template>
  <section>
    <p
      v-if="loadError"
      class="error"
      role="alert"
    >
      {{ loadError }}
    </p>
    <p
      v-else-if="!call"
      class="muted"
    >
      Loading…
    </p>

    <template v-else>
      <h1>{{ call.title }}</h1>
      <p class="muted">
        <span v-if="call.language">Language: {{ languageLabel(call.language) }}</span>
        <span v-if="call.duration_s"> · {{ formatDuration(call.duration_s) }}</span>
      </p>

      <template v-if="isActive(call.status)">
        <ProgressBar
          :value="call.progress"
          :label="statusLabel(call)"
        />
        <div class="row">
          <button
            class="button secondary"
            @click="cancel"
          >
            Cancel
          </button>
        </div>
      </template>

      <template v-else-if="call.status === 'failed'">
        <p
          class="error"
          role="alert"
        >
          {{ call.error_message }}
        </p>
        <div class="row">
          <button
            v-if="call.audio_available"
            class="button"
            @click="retry"
          >
            Try again
          </button>
          <button
            class="button secondary"
            @click="remove"
          >
            Delete
          </button>
        </div>
      </template>

      <template v-else-if="call.status === 'cancelled'">
        <p>Transcription cancelled. The recording was removed from this computer.</p>
        <div class="row">
          <NuxtLink
            to="/new"
            class="button"
          >
            Upload again
          </NuxtLink>
          <button
            class="button secondary"
            @click="remove"
          >
            Delete
          </button>
        </div>
      </template>

      <template v-else>
        <p class="muted">
          {{ call.audio_available ? 'The audio file is kept on this computer.' : 'The audio file was deleted after transcription.' }}
        </p>

        <h2>Proposal draft</h2>

        <aside
          v-if="profileKnown && !hasProfile"
          class="notice"
          role="note"
        >
          <strong>Set up your profile first.</strong>
          The draft uses your services, rates and payment terms.
          <NuxtLink to="/profile">
            Set up my profile
          </NuxtLink>
        </aside>

        <template v-else>
          <template v-if="draft && isDraftActive(draft.status)">
            <ProgressBar
              :value="draft.progress"
              :label="draftStatusLabel(draft)"
            />
            <div class="row">
              <button
                class="button secondary"
                :disabled="cancelling"
                @click="onCancelDraft"
              >
                {{ cancelling ? 'Cancelling…' : 'Cancel' }}
              </button>
            </div>
          </template>

          <template v-else>
            <p
              v-if="draft?.status === 'failed'"
              class="error"
              role="alert"
            >
              {{ draft.error_message }}
            </p>
            <p v-else-if="draft?.status === 'cancelled'">
              The draft was cancelled.
            </p>
            <div
              v-if="canStart && !editing"
              class="row"
            >
              <label>
                Write it in
                <select v-model="language">
                  <option value="">
                    The language of the call{{ call.language ? ` (${languageLabel(call.language)})` : '' }}
                  </option>
                  <option
                    v-for="option in PROPOSAL_LANGUAGES"
                    :key="option.code"
                    :value="option.code"
                  >
                    {{ option.label }}
                  </option>
                </select>
              </label>
              <button
                class="button"
                @click="draftAgain"
              >
                {{ draft?.status === 'done' ? 'Draft again' : draft ? 'Try again' : 'Draft proposal' }}
              </button>
            </div>
          </template>

          <p
            v-if="draftError && !editing"
            class="error"
            role="alert"
          >
            {{ draftError }}
          </p>

          <template v-if="draft?.status === 'done' && draft.proposal">
            <p
              v-if="draft.warnings.length"
              class="muted"
            >
              Some items had no source in the call and are marked “Assumption”. Check them before sending.
            </p>
            <p class="muted">
              Click a time next to an item to see what was said in the call.
            </p>

            <div
              v-if="!editing"
              class="row"
            >
              <button
                class="button"
                @click="startEditing"
              >
                Edit proposal
              </button>
              <button
                class="button secondary"
                @click="download('md')"
              >
                Download Markdown
              </button>
              <button
                class="button secondary"
                @click="download('pdf')"
              >
                Download PDF
              </button>
              <span
                v-if="justSaved"
                role="status"
                class="muted"
              >Changes saved.</span>
            </div>
            <ProposalView
              v-if="!editing"
              :sections="draft.proposal.sections"
              @show="showInTranscript"
            />
            <template v-else>
              <ProposalEditor
                v-model="editSections"
                @show="showInTranscript"
              />
              <p
                v-if="draftError"
                class="error"
                role="alert"
              >
                {{ draftError }}
              </p>
              <div class="row">
                <button
                  class="button"
                  :disabled="saving || !dirty"
                  @click="saveChanges"
                >
                  {{ saving ? 'Saving…' : 'Save changes' }}
                </button>
                <button
                  class="button secondary"
                  :disabled="saving"
                  @click="discardEditing"
                >
                  Discard changes
                </button>
                <span
                  v-if="dirty"
                  class="muted"
                >You have unsaved changes. Downloads use the saved version.</span>
              </div>
            </template>
            <details v-if="draft.notes">
              <summary>What the draft is based on</summary>
              <NotesView
                :notes="draft.notes"
                @show="showInTranscript"
              />
            </details>
          </template>
        </template>

        <details
          :open="transcriptOpen"
          @toggle="transcriptOpen = ($event.target as HTMLDetailsElement).open"
        >
          <summary>Transcript</summary>
          <TranscriptView
            :segments="transcript?.segments ?? []"
            :highlight-id="highlightId"
          />
        </details>

        <div class="row">
          <button
            class="button secondary"
            @click="remove"
          >
            Delete call
          </button>
        </div>
      </template>
    </template>
  </section>
</template>

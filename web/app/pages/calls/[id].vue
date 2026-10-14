<script setup lang="ts">
import type { ProposalSection } from '~/types/api'

const route = useRoute()
const id = String(route.params.id)
const api = useCalls()
const profileApi = useProfile()
const format = useFormat()
const errors = useErrors()
const { call, transcript, unreachable, cancel, retry } = useCallStatus(id)
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
const wide = useWideScreen()
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

const pdfAllowed = computed(() => canExportPdf(draft.value?.proposal?.language))
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
  if (!window.confirm(format.t('call.confirmDelete'))) return
  await api.remove(id)
  await navigateTo('/')
}

async function draftAgain() {
  if (draft.value?.status === 'done' && !window.confirm(format.t('call.confirmRedraft'))) return
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
  if (dirty.value && !window.confirm(format.t('call.confirmDiscard'))) return
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

onBeforeRouteLeave(() => !dirty.value || window.confirm(format.t('call.confirmLeave')))

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
      v-if="unreachable" class="error" role="alert" > {{ $t('errors.engineUnreachable') }}
    </p>
    <p
      v-else-if="!call"
      class="muted"
    >
      {{ $t('common.loading') }}
    </p>

    <template v-else>
      <h1 dir="auto">{{ call.title }}</h1>
      <p class="muted">
        <span v-if="call.language">{{ $t('call.language', { language: format.language(call.language) }) }}</span>
        <span v-if="call.duration_s"> · {{ format.duration(call.duration_s) }}</span>
      </p>

      <template v-if="isActive(call.status)">
        <ProgressBar
          :value="call.progress"
          :label="format.callStatus(call)"
        />
        <div class="row">
          <button
            class="button secondary"
            @click="cancel"
          >
            {{ $t('common.cancel') }}
          </button>
        </div>
      </template>

      <template v-else-if="call.status === 'failed'">
        <p
          class="error"
          role="alert"
        >
          {{ errors.job(call.error_code, call.error_message) }}
        </p>
        <div class="row">
          <button
            v-if="call.audio_available"
            class="button"
            @click="retry"
          >
            {{ $t('common.tryAgain') }}
          </button>
          <button
            class="button secondary"
            @click="remove"
          >
            {{ $t('common.delete') }}
          </button>
        </div>
      </template>

      <template v-else-if="call.status === 'cancelled'">
        <p>{{ $t('call.cancelledNote') }}</p>
        <div class="row">
          <NuxtLink
            to="/new"
            class="button"
          >
            {{ $t('call.uploadAgain') }}
          </NuxtLink>
          <button
            class="button secondary"
            @click="remove"
          >
            {{ $t('common.delete') }}
          </button>
        </div>
      </template>

      <template v-else>
        <div :class="['call-layout', { 'with-pane': wide }]">
          <div>
            <p class="muted">
              {{ call.audio_available ? $t('call.audioKept') : $t('call.audioDeleted') }}
            </p>

            <h2>{{ $t('call.proposalDraft') }}</h2>

            <aside
              v-if="profileKnown && !hasProfile"
              class="notice"
              role="note"
            >
              <strong>{{ $t('profileNotice.title') }}</strong> {{ $t('call.profileNotice') }} <NuxtLink to="/profile"> {{ $t('profileNotice.link') }} </NuxtLink>
            </aside>

            <template v-else>
              <template v-if="draft && isDraftActive(draft.status)">
                <ProgressBar
                  :value="draft.progress"
                  :label="format.draftStatus(draft)"
                />
                <div class="row">
                  <button
                    class="button secondary"
                    :disabled="cancelling"
                    @click="onCancelDraft"
                  >
                    {{ cancelling ? $t('common.cancelling') : $t('common.cancel') }}
                  </button>
                </div>
              </template>

              <template v-else>
                <p
                  v-if="draft?.status === 'failed'"
                  class="error"
                  role="alert"
                >
                  {{ errors.job(draft.error_code, draft.error_message) }}
                </p>
                <p v-else-if="draft?.status === 'cancelled'">
                  {{ $t('call.draftCancelled') }}
                </p>
                <div
                  v-if="canStart && !editing"
                  class="row"
                >
                  <label>
                    {{ $t('call.writeIn') }}
                    <select v-model="language">
                      <option value="">
                        {{ call.language ? $t('call.callLanguageNamed', { language: format.language(call.language) }) : $t('call.callLanguage') }}
                      </option>
                      <option
                        v-for="code in PROPOSAL_LANGUAGES" :key="code" :value="code" > {{ format.language(code) }}
                      </option>
                    </select>
                  </label>
                  <button
                    class="button"
                    @click="draftAgain"
                  >
                    {{ draft?.status === 'done' ? $t('call.draftAgain') : draft ? $t('common.tryAgain') : $t('call.draft') }}
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
                  {{ $t('call.warnings') }}
                </p>
                <p class="muted">
                  {{ $t('call.sourceHint') }}
                </p>

                <div
                  v-if="!editing"
                  class="row"
                >
                  <button
                    class="button"
                    @click="startEditing"
                  >
                    {{ $t('call.edit') }}
                  </button>
                  <button
                    class="button secondary"
                    @click="download('md')"
                  >
                    {{ $t('call.downloadMd') }}
                  </button>
                  <button
                    class="button secondary"
                    :disabled="!pdfAllowed"
                    :title="pdfAllowed ? undefined : $t('call.pdfUnsupported')"
                    @click="download('pdf')"
                  >
                    {{ $t('call.downloadPdf') }}
                  </button>
                  <span
                    v-if="justSaved"
                    role="status"
                    class="muted"
                  >{{ $t('call.saved') }}</span>
                </div>
                <p
                  v-if="!editing && !pdfAllowed"
                  class="muted"
                >
                  {{ $t('call.pdfUnsupported') }}
                </p>
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
                      {{ saving ? $t('common.saving') : $t('call.saveChanges') }}
                    </button>
                    <button
                      class="button secondary"
                      :disabled="saving"
                      @click="discardEditing"
                    >
                      {{ $t('call.discard') }}
                    </button>
                    <span
                      v-if="dirty"
                      class="muted"
                    >{{ $t('call.unsaved') }}</span>
                  </div>
                </template>
                <details v-if="draft.notes">
                  <summary>{{ $t('call.basedOn') }}</summary>
                  <NotesView
                    :notes="draft.notes"
                    @show="showInTranscript"
                  />
                </details>
              </template>
            </template>

            <details
              v-if="!wide"
              :open="transcriptOpen"
              @toggle="transcriptOpen = ($event.target as HTMLDetailsElement).open"
            >
              <summary>{{ $t('call.transcript') }}</summary>
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
                {{ $t('call.delete') }}
              </button>
            </div>
          </div>
          <aside
            v-if="wide"
            class="transcript-pane"
            :aria-label="$t('call.transcript')"
          >
            <h2>{{ $t('call.transcript') }}</h2>
            <TranscriptView
              :segments="transcript?.segments ?? []"
              :highlight-id="highlightId"
            />
          </aside>
        </div>
      </template>
    </template>
  </section>
</template>

import type { Profile } from '~/types/api'
import { choicesFromProfile, choicesToProfile, type SectionChoice } from '~/utils/sections'

/** The profile as the form edits it: multi-line text boxes instead of lists. */
export interface ProfileFormState {
  name: string
  servicesText: string
  hourlyRate: string
  projectRatesText: string
  paymentTerms: string
  tone: string
  sections: SectionChoice[]
}

export function emptyProfileForm(): ProfileFormState {
  return {
    name: '',
    servicesText: '',
    hourlyRate: '',
    projectRatesText: '',
    paymentTerms: '',
    tone: '',
    sections: choicesFromProfile([]),
  }
}

const lines = (text: string) => text.split('\n').map(l => l.trim()).filter(Boolean)

export function formFromProfile(profile: Profile): ProfileFormState {
  return {
    name: profile.name,
    servicesText: profile.services.join('\n'),
    hourlyRate: profile.hourly_rate ?? '',
    projectRatesText: profile.project_rates.join('\n'),
    paymentTerms: profile.payment_terms,
    tone: profile.tone,
    sections: choicesFromProfile(profile.sections),
  }
}

export function profileFromForm(form: ProfileFormState): Profile {
  return {
    name: form.name.trim(),
    services: lines(form.servicesText),
    hourly_rate: form.hourlyRate.trim() || null,
    project_rates: lines(form.projectRatesText),
    payment_terms: form.paymentTerms.trim(),
    sections: choicesToProfile(form.sections),
    tone: form.tone.trim(),
  }
}

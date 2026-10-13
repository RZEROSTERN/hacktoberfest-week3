import { describe, expect, it } from 'vitest'
import type { Profile } from '../app/types/api'
import { emptyProfileForm, formFromProfile, profileFromForm } from '../app/utils/profileForm'

const profile: Profile = {
  name: 'Ana Pérez',
  services: ['Sitios web', 'Reservaciones'],
  hourly_rate: '650 MXN por hora',
  project_rates: ['Sitio de hasta 5 secciones: 24,000 MXN'],
  payment_terms: '50% de anticipo.',
  sections: [],
  tone: 'cercano',
}

describe('profile form', () => {
  it('round-trips a profile', () => {
    expect(profileFromForm(formFromProfile(profile))).toEqual(profile)
  })

  it('turns text boxes into trimmed lists and drops empty lines', () => {
    const form = { ...emptyProfileForm(), name: '  Ana ', servicesText: ' Web \n\n Apps \n', projectRatesText: '\n', hourlyRate: '  ' }
    expect(profileFromForm(form)).toMatchObject({ name: 'Ana', services: ['Web', 'Apps'], project_rates: [], hourly_rate: null })
  })

  it('starts empty with every section on', () => {
    const form = emptyProfileForm()
    expect(form.name).toBe('')
    expect(form.sections.every(s => s.enabled)).toBe(true)
  })
})

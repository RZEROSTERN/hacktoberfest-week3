import type { Profile } from '~/types/api'

export function useProfile() {
  const { apiFetch } = useApi()

  /** The saved profile, or null when none has been set up yet. */
  async function load(): Promise<Profile | null> {
    try {
      return await apiFetch<Profile>('/profile')
    } catch (error) {
      if ((error as { statusCode?: number }).statusCode === 404) return null
      throw error
    }
  }

  function save(profile: Profile) {
    return apiFetch<Profile>('/profile', { method: 'PUT', body: profile })
  }

  return { load, save }
}

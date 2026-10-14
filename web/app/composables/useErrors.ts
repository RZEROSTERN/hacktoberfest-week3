import { apiErrorText, codeErrorText, readApiError, UploadError, type ApiErrorInfo } from '~/utils/apiError'

/** Turns what went wrong into a sentence in the current language. */
export function useErrors() {
  const { t, exists } = useFormat()

  // The api names a section by its id ("scope"): say it with the section's name in this language.
  function describe(params: Record<string, unknown>) {
    const where = params.where
    return typeof where === 'string' && exists(`sections.${where}`) ? { ...params, where: t(`sections.${where}`) } : params
  }

  function fromInfo(info: ApiErrorInfo, fallbackKey: string) {
    return apiErrorText(info, t, exists, fallbackKey, describe)
  }

  return {
    /** A thrown error (a refused request, a failed upload, a network failure). `fallbackKey` says what was attempted. */
    message(error: unknown, fallbackKey: string): string {
      if (error instanceof UploadError && error.kind === 'unreachable') return t('errors.engineUnreachable')
      if (error instanceof UploadError && error.kind === 'cancelled') return t('errors.uploadCancelled')
      return fromInfo(readApiError(error), fallbackKey)
    },
    fromInfo,
    /** A background job that failed: its error code, and the api's English message as a last resort. */
    job: (code: string | null, message: string | null) => codeErrorText(code, message, t, exists),
  }
}

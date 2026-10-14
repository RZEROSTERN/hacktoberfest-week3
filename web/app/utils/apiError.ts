import type { Translate } from '~/utils/intl'

/** What the api says about a refused request: a stable code, values for the message, and its English text. */
export interface ApiErrorInfo {
  status: number
  code: string | null
  params: Record<string, unknown>
  /** The api's own English message: shown only when the app has no translation for the code. */
  detail: string | null
}

/** A failed upload: what the api answered, or why there was no answer. */
export class UploadError extends Error {
  constructor(
    readonly info: ApiErrorInfo,
    readonly kind: 'refused' | 'unreachable' | 'cancelled' = 'refused',
  ) {
    super(info.detail ?? `upload failed (${info.status})`)
  }
}

/** The body of an error response (`{detail, code, params}`) read into an ApiErrorInfo. */
export function parseErrorBody(body: unknown, status: number): ApiErrorInfo {
  const data = (body ?? {}) as { detail?: unknown, code?: unknown, params?: unknown }
  return {
    status,
    code: typeof data.code === 'string' ? data.code : null,
    params: data.params && typeof data.params === 'object' ? (data.params as Record<string, unknown>) : {},
    detail: typeof data.detail === 'string' ? data.detail : null,
  }
}

/** Whatever was thrown (a fetch error, an upload error, a plain Error) as an ApiErrorInfo. */
export function readApiError(error: unknown): ApiErrorInfo {
  if (error instanceof UploadError) return error.info
  const e = error as { data?: unknown, statusCode?: number } | null
  return parseErrorBody(e?.data, e?.statusCode ?? 0)
}

/**
 * The message to show. The code is translated when the app knows it, with the api's values filled in;
 * otherwise the api's English text, otherwise the generic message for what was being attempted.
 */
export function apiErrorText(
  info: ApiErrorInfo,
  t: Translate,
  exists: (key: string) => boolean,
  fallbackKey: string,
  describe: (params: Record<string, unknown>) => Record<string, unknown> = p => p,
): string {
  if (info.code && exists(`apiErrors.${info.code}`)) return t(`apiErrors.${info.code}`, describe(info.params))
  return info.detail ?? t(fallbackKey)
}

/** A job that failed carries `error_code` and an English `error_message`. Same rule, no values. */
export function codeErrorText(code: string | null, message: string | null, t: Translate, exists: (key: string) => boolean): string {
  if (code && exists(`apiErrors.${code}`)) return t(`apiErrors.${code}`)
  return message ?? t('errors.generic')
}

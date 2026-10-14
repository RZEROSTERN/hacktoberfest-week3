import { describe, expect, it } from 'vitest'
import { apiErrorText, codeErrorText, parseErrorBody, readApiError, UploadError } from '../app/utils/apiError'
import { translator } from './support/translator'

const t = translator('en')
const exists = (key: string) => { try { t(key); return key.startsWith('apiErrors.') ? key.slice(10) in { call_not_found: 1, edit_prices_outside_investment: 1, cloud_model: 1 } : true } catch { return false } }

describe('reading what the api said', () => {
  it('takes the code, the values and the English text out of an error body', () => {
    const info = parseErrorBody({ detail: 'Call not found.', code: 'call_not_found', params: {} }, 404)
    expect(info).toEqual({ status: 404, code: 'call_not_found', params: {}, detail: 'Call not found.' })
  })

  it('copes with a body that is not what the api normally sends', () => {
    expect(parseErrorBody(null, 500)).toEqual({ status: 500, code: null, params: {}, detail: null })
    expect(parseErrorBody({ detail: { nested: true } }, 422).detail).toBeNull()
  })

  it('reads a fetch error, an upload error and a plain failure', () => {
    expect(readApiError({ statusCode: 422, data: { detail: 'x', code: 'cloud_model', params: {} } }).code).toBe('cloud_model')
    const upload = new UploadError(parseErrorBody({ detail: 'x', code: 'file_empty', params: {} }, 400))
    expect(readApiError(upload).code).toBe('file_empty')
    expect(readApiError(new Error('boom'))).toMatchObject({ code: null, detail: null, status: 0 })
  })
})

describe('apiErrorText', () => {
  it('translates a code it knows, filling in the values', () => {
    const info = parseErrorBody({ detail: 'English', code: 'edit_prices_outside_investment', params: { where: 'scope' } }, 422)
    expect(apiErrorText(info, t, exists, 'errors.generic')).toBe('Prices belong in the investment section only, not in scope.')
  })

  it('shows the api\'s own English when the app has no translation for the code', () => {
    const info = parseErrorBody({ detail: 'Something new happened.', code: 'brand_new_code', params: {} }, 409)
    expect(apiErrorText(info, t, exists, 'errors.generic')).toBe('Something new happened.')
  })

  it('says what was being attempted when there is nothing else to say', () => {
    expect(apiErrorText(parseErrorBody(null, 0), t, exists, 'errors.draftStart')).toBe('The draft could not be started.')
  })

  it('lets the caller reword the values, for example a section id as the section\'s name', () => {
    const info = parseErrorBody({ detail: 'x', code: 'edit_prices_outside_investment', params: { where: 'scope' } }, 422)
    const text = apiErrorText(info, t, exists, 'errors.generic', p => ({ ...p, where: 'Alcance' }))
    expect(text).toContain('Alcance')
  })
})

describe('codeErrorText', () => {
  it('translates a failed job by its code and falls back to the api\'s message', () => {
    expect(codeErrorText('cloud_model', 'English', t, exists)).toContain('Cloud models')
    expect(codeErrorText('unheard_of', 'English text', t, exists)).toBe('English text')
    expect(codeErrorText(null, null, t, exists)).toBe('Something went wrong.')
  })
})

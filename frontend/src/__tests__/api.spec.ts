import { describe, expect, it } from 'vitest'

import { ApiError, queryString } from '@/api'

describe('queryString', () => {
  it('builds the query and skips empty values', () => {
    expect(queryString({ page: 2, search: 'ana souza', ordering: '', x: null, y: undefined })).toBe(
      '?page=2&search=ana+souza',
    )
  })

  it('returns an empty string when there is nothing to send', () => {
    expect(queryString({ search: '' })).toBe('')
  })
})

describe('ApiError.fieldErrors', () => {
  it('returns DRF validation messages per field', () => {
    const error = new ApiError(400, 'Bad Request', { email: ['Taken.'], detail: 'x' })
    expect(error.fieldErrors()).toEqual({ email: ['Taken.'] })
  })

  it('is empty for non-validation errors', () => {
    expect(new ApiError(500, 'boom', { email: ['x'] }).fieldErrors()).toEqual({})
    expect(new ApiError(400, 'bad', null).fieldErrors()).toEqual({})
  })
})

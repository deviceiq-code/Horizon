/** HTTP client for the Django backend: sends the session cookie, CSRF token and language. */

import { currentLanguage } from '@/i18n'

export class ApiError extends Error {
  status: number
  /** Parsed JSON error body, e.g. DRF validation errors: { field: ["message", ...] } */
  data: unknown

  constructor(status: number, message: string, data: unknown = null) {
    super(message)
    this.status = status
    this.data = data
  }

  /** Validation messages per field (400 responses from DRF serializers). */
  fieldErrors(): Record<string, string[]> {
    if (this.status !== 400 || typeof this.data !== 'object' || this.data === null) return {}
    return Object.fromEntries(
      Object.entries(this.data).filter(([, v]) => Array.isArray(v)) as [string, string[]][],
    )
  }
}

/** Shape of paginated list responses (config/pagination.py). */
export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

/** Parameters accepted by every list endpoint (search, ordering and pagination). */
export interface ListParams {
  page: number
  pageSize: number
  search?: string
  /** Field name, prefixed with "-" for descending (e.g. "-email") */
  ordering?: string
  /** Endpoint-specific filters, sent as they are (e.g. { is_enabled: true }) */
  filters?: Record<string, string | number | boolean>
}

/** Query string for a list endpoint, in the backend's parameter names. */
export function listQuery(params: ListParams): string {
  const filters = Object.fromEntries(
    Object.entries(params.filters ?? {}).map(([key, value]) => [key, String(value)]),
  )
  return queryString({
    page: params.page,
    page_size: params.pageSize,
    search: params.search?.trim(),
    ordering: params.ordering,
    ...filters,
  })
}

/** Message for a failed delete: the server's reason when it refused (409), else `fallback`. */
export function deleteErrorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError && error.status === 409 && error.message
    ? error.message
    : fallback
}

/** Build "?a=1&b=2", skipping empty values. */
export function queryString(params: Record<string, string | number | null | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') search.set(key, String(value))
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

function readCookie(name: string): string | null {
  const m = document.cookie.match(new RegExp('(^|;\\s*)' + name + '=([^;]*)'))
  return m && m[2] ? decodeURIComponent(m[2]) : null
}

export async function api<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase()
  const headers = new Headers(options.headers)
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  // Backend messages in the UI language (for logged-in users the saved language wins)
  if (!headers.has('Accept-Language')) {
    headers.set('Accept-Language', currentLanguage())
  }
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const token = readCookie('csrftoken')
    if (token) headers.set('X-CSRFToken', token)
  }

  const resp = await fetch(`/api${path}`, {
    ...options,
    method,
    headers,
    credentials: 'same-origin',
  })

  if (!resp.ok) {
    let message = resp.statusText
    let data: unknown = null
    try {
      data = await resp.json()
      if (data && typeof data === 'object' && 'detail' in data && typeof data.detail === 'string') {
        message = data.detail
      }
    } catch {
      /* response without a JSON body */
    }
    throw new ApiError(resp.status, message, data)
  }
  if (resp.status === 204) return undefined as T
  return (await resp.json()) as T
}

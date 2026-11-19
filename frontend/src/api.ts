/** HTTP client for the Django backend: sends the session cookie, CSRF token and language. */

import { currentLanguage } from '@/i18n'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
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
    try {
      const data = await resp.json()
      message = data.detail ?? message
    } catch {
      /* response without a JSON body */
    }
    throw new ApiError(resp.status, message)
  }
  if (resp.status === 204) return undefined as T
  return (await resp.json()) as T
}

/**
 * Environments: Live and Development (Test) — the same system over different databases
 * (backend config/environments.py). The login page chooses one; it is kept in a cookie that
 * every request sends, so the backend serves that environment's database and files.
 */

import { api, readCookie } from '@/api'

export const LIVE = 'live'
export const COOKIE_NAME = 'horizon_environment'
export const ENVIRONMENT_ICONS: Record<string, string> = {
  live: 'mdi-check-decagram-outline',
  development: 'mdi-flask-outline',
}

/** Remembered for the next sign-in: one year */
const MAX_AGE = 60 * 60 * 24 * 365

export interface Environments {
  /** Configured on the server, in the order offered (only Live: no choice to make) */
  environments: string[]
  /** The one in use */
  current: string
}

export function fetchEnvironments(): Promise<Environments> {
  return api<Environments>('/auth/environments/')
}

/** The environment the browser asks for (Live when none was chosen). */
export function chosenEnvironment(): string {
  return readCookie(COOKIE_NAME) ?? LIVE
}

/** Ask for `name` from now on (the session of the other environment is not used any more). */
export function chooseEnvironment(name: string): void {
  const secure = window.location.protocol === 'https:' ? '; Secure' : ''
  document.cookie = `${COOKIE_NAME}=${encodeURIComponent(name)}; Path=/; Max-Age=${MAX_AGE}; SameSite=Lax${secure}`
}

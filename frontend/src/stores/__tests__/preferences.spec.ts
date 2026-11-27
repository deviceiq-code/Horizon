import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '@/api'
import { currentLanguage, setLanguage } from '@/i18n'
import { usePreferencesStore } from '@/stores/preferences'

vi.mock('@/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api')>()),
  api: vi.fn<typeof api>(),
}))

const apiMock = vi.mocked(api)

describe('preferences store', () => {
  beforeEach(() => {
    localStorage.clear()
    setLanguage('en')
    setActivePinia(createPinia())
    apiMock.mockReset()
  })

  it('applies language and theme to the UI and stores them in the browser', () => {
    const store = usePreferencesStore()
    store.apply({ language: 'pt-br', theme: 'dark' })
    expect(currentLanguage()).toBe('pt-br')
    expect(document.documentElement.lang).toBe('pt-br')
    expect(store.theme).toBe('dark')
    expect(localStorage.getItem('horizon.language')).toBe('pt-br')
    expect(localStorage.getItem('horizon.theme')).toBe('dark')
  })

  it('ignores an unsupported language', () => {
    const store = usePreferencesStore()
    store.apply({ language: 'xx' })
    expect(store.language).toBe('en')
  })

  it('saves to the account sending only what changed', async () => {
    apiMock.mockResolvedValue({ language: 'es', theme: 'system', updated_at: '' })
    const store = usePreferencesStore()
    await store.save({ language: 'es' })
    expect(apiMock).toHaveBeenCalledWith('/auth/preferences/', {
      method: 'PATCH',
      body: JSON.stringify({ language: 'es' }),
    })
    expect(store.language).toBe('es')
    expect(currentLanguage()).toBe('es')
  })

  it('rolls back the change if the API fails', async () => {
    apiMock.mockRejectedValue(new ApiError(500, 'server failure'))
    const store = usePreferencesStore()
    await expect(store.save({ language: 'pt-br', theme: 'dark' })).rejects.toThrow('server failure')
    expect(store.language).toBe('en')
    // Back to the default: light mode
    expect(store.theme).toBe('light')
    expect(currentLanguage()).toBe('en')
  })
})

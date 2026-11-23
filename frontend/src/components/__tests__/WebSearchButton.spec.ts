import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { h, ref } from 'vue'
import { VTextField } from 'vuetify/components'

import { usePreferencesStore } from '@/stores/preferences'
import { inBody, mountWithPlugins, settle } from '@/test-utils'
import { webSearchUrl } from '@/webSearch'
import WebSearchButton from '../WebSearchButton.vue'

describe('WebSearchButton', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => vi.restoreAllMocks())

  it('builds the search address of each engine', () => {
    expect(webSearchUrl('google', '  John Deere 5060E ')).toBe(
      'https://www.google.com/search?q=John%20Deere%205060E',
    )
    expect(webSearchUrl('yahoo', 'a&b')).toBe('https://search.yahoo.com/search?p=a%26b')
    expect(webSearchUrl('duckduckgo', '   ')).toBeNull()
  })

  it("opens a new tab with the user's engine; disabled while the field is empty", async () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null)
    const term = ref('')
    const wrapper = mountWithPlugins({
      render: () =>
        h(
          VTextField,
          { modelValue: term.value },
          {
            'append-inner': () => h(WebSearchButton, { term: term.value }),
          },
        ),
    })
    await settle()
    const button = () => inBody('[data-testid="web-search"]') as HTMLButtonElement
    expect(button().disabled).toBe(true)
    expect(button().getAttribute('tabindex')).toBe('-1')

    term.value = 'Caterpillar 320 GC'
    usePreferencesStore().apply({ web_search_engine: 'bing' })
    await settle()
    expect(button().disabled).toBe(false)
    expect(button().title).toBe('Search the Internet (Bing)')
    button().click()
    expect(open).toHaveBeenCalledWith(
      'https://www.bing.com/search?q=Caterpillar%20320%20GC',
      '_blank',
      'noopener,noreferrer',
    )
    wrapper.unmount()
  })
})

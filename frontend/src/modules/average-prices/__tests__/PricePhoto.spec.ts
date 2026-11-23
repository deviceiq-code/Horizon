import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { h } from 'vue'

import { setLanguage } from '@/i18n'
import { inBody, mountWithPlugins, settle } from '@/test-utils'
import PricePhoto from '../PricePhoto.vue'

function mountPhoto(photoId: number | null, sourceUrl = '') {
  return mountWithPlugins({
    render: () =>
      h(PricePhoto, {
        rowId: 100,
        photoId,
        icon: 'mdi-excavator',
        title: 'Caterpillar 320 GC',
        sourceUrl,
      }),
  })
}

describe('PricePhoto', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('shows the icon without a photo; nothing to change here (that is in the form)', async () => {
    const wrapper = mountPhoto(null)
    await settle()
    expect(inBody('.mdi-excavator')).not.toBeNull()
    expect(inBody('[data-testid="photo-upload"]')).toBeNull()
    expect(inBody('[data-testid="photo-remove"]')).toBeNull()
    wrapper.unmount()
  })

  it('enlarges the photo, linking to where it was found', async () => {
    const wrapper = mountPhoto(31, 'https://www.cat.com/320')
    await settle()
    expect(inBody('[data-testid="photo-thumb"] img')!.getAttribute('src')).toBe(
      '/api/average-prices/100/photo/?v=31',
    )
    inBody('[data-testid="photo-thumb"]')!.click()
    await settle()
    expect(inBody('[data-testid="photo-large"]')).not.toBeNull()
    const link = inBody('[data-testid="photo-source"]') as HTMLAnchorElement
    expect(link.getAttribute('href')).toBe('https://www.cat.com/320')
    expect(link.getAttribute('target')).toBe('_blank')
    wrapper.unmount()
  })
})

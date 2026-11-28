import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { i18n, setLanguage } from '@/i18n'
import vuetify from '@/plugins/vuetify'
import FormDialog from '../FormDialog.vue'

describe('FormDialog audit', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
  })

  it('a record being edited shows who created it and who changed it last', async () => {
    const wrapper = mount(FormDialog, {
      props: {
        modelValue: true,
        title: 'Edit',
        audit: {
          created_at: '2026-11-20T10:00:00Z',
          created_by_name: 'Ana Souza',
          updated_at: '2026-11-28T15:00:00Z',
          updated_by_name: null,
        },
      },
      attachTo: document.body,
      global: { plugins: [vuetify, i18n] },
    })
    await new Promise((r) => setTimeout(r, 0))
    const audit = document.querySelector('[data-testid="form-dialog-audit"]')!.textContent!
    expect(audit).toContain('by Ana Souza')
    expect(audit).toContain('Changed on')
    expect(audit).toContain('by —') // changed before it was recorded
    wrapper.unmount()
    document.body.innerHTML = ''
  })

  it('a new record shows nothing', async () => {
    const wrapper = mount(FormDialog, {
      props: { modelValue: true, title: 'New' },
      attachTo: document.body,
      global: { plugins: [vuetify, i18n] },
    })
    await new Promise((r) => setTimeout(r, 0))
    expect(document.querySelector('[data-testid="form-dialog-audit"]')).toBeNull()
    wrapper.unmount()
    document.body.innerHTML = ''
  })
})

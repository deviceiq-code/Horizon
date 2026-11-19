/** Helpers for component tests that mount real Vuetify components. */
import { flushPromises, mount } from '@vue/test-utils'
import type { Component } from 'vue'

import { i18n } from '@/i18n'
import vuetify from '@/plugins/vuetify'

/** Mount a page with Vuetify and i18n, attached to <body> so dialogs can be found. */
export function mountWithPlugins(component: Component) {
  return mount(component, {
    attachTo: document.body,
    global: { plugins: [vuetify, i18n] },
  })
}

/** Dialogs and menus are teleported to <body>, outside the component's own DOM. */
export function inBody(selector: string) {
  return document.body.querySelector<HTMLElement>(selector)
}

/** Let pending promises, timers and re-renders finish. */
export async function settle() {
  await flushPromises()
  await new Promise((r) => setTimeout(r, 0))
  await flushPromises()
}

/**
 * Type into a field (by data-testid) and let Vue/Vuetify react, like a real user would.
 * Firing several inputs and a click without settling in between makes Vuetify's async
 * validation race and report stale errors.
 */
export async function typeInto(testId: string, value: string) {
  const input = inBody(`[data-testid="${testId}"] input`) as HTMLInputElement
  input.value = value
  input.dispatchEvent(new Event('input'))
  await settle()
}

/** Titles currently offered in the open dropdown of an autocomplete/select. */
export function dropdownOptions(): string[] {
  return [...document.body.querySelectorAll('.v-overlay--active .v-list-item-title')].map(
    (el) => el.textContent?.trim() ?? '',
  )
}

/** Open the dropdown of an autocomplete/select (by data-testid). */
export async function openDropdown(testId: string) {
  inBody(`[data-testid="${testId}"] .v-field`)!.dispatchEvent(
    new MouseEvent('mousedown', { bubbles: true }),
  )
  await settle()
}

/** Open an autocomplete/select (by data-testid) and click the option with this title. */
export async function pickOption(testId: string, title: string) {
  await openDropdown(testId)
  const option = [
    ...document.body.querySelectorAll<HTMLElement>('.v-overlay--active .v-list-item'),
  ].find((el) => el.querySelector('.v-list-item-title')?.textContent?.trim() === title)
  if (!option)
    throw new Error(`Option "${title}" not offered; got: ${dropdownOptions().join(', ')}`)
  option.click()
  await settle()
}

export async function click(testId: string) {
  inBody(`[data-testid="${testId}"]`)!.click()
  await settle()
}

import { afterEach, describe, expect, it } from 'vitest'
import { installSelectOnFocus } from '../smartTools'

function field(html: string) {
  document.body.innerHTML = html
  return document.body.firstElementChild as HTMLInputElement | HTMLTextAreaElement
}
const selected = (el: HTMLInputElement | HTMLTextAreaElement) =>
  el.value.slice(el.selectionStart ?? 0, el.selectionEnd ?? 0)

describe('Smart Tools: select on focus', () => {
  let cleanup = () => {}
  afterEach(() => {
    cleanup()
    document.body.innerHTML = ''
  })

  it("entering a text field selects its content; a click's mouse up keeps it", () => {
    cleanup = installSelectOnFocus(() => true)
    const input = field('<input type="text" value="12.371,91">')
    input.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    input.focus()
    expect(selected(input)).toBe('12.371,91')
    const up = new MouseEvent('mouseup', { bubbles: true, cancelable: true })
    input.dispatchEvent(up)
    expect(up.defaultPrevented).toBe(true)
  })

  it('leaves multi-line, read-only fields alone, and does nothing when turned off', () => {
    let on = true
    cleanup = installSelectOnFocus(() => on)
    const area = field('<textarea>Fleet of trucks</textarea>')
    area.focus()
    expect(selected(area)).toBe('')
    const readonly = field('<input type="text" value="IT" readonly>')
    readonly.focus()
    expect(selected(readonly)).toBe('')
    on = false
    const input = field('<input type="text" value="36">')
    input.focus()
    expect(selected(input)).toBe('')
  })
})

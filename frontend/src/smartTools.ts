/**
 * Smart Tools: conveniences of the interface the user turns on or off in Settings.
 *
 * Select on focus: entering a single-line text field (click or Tab) selects its content, so
 * typing replaces it. Multi-line fields (textarea) are left alone. A click would collapse the
 * selection on mouse up: that mouse up is ignored for the field just entered. Empty fields have
 * nothing to select.
 */

/** Text-like inputs (number fields cannot be selected) */
const TEXT_TYPES = new Set(['', 'text', 'search', 'email', 'tel', 'url', 'password'])

function selectable(target: EventTarget | null): target is HTMLInputElement {
  return (
    target instanceof HTMLInputElement &&
    TEXT_TYPES.has(target.type) &&
    !target.readOnly &&
    !target.disabled
  )
}

/** Installs the listeners on the document; `enabled` is read on each focus. Returns a cleanup. */
export function installSelectOnFocus(enabled: () => boolean, root: Document = document) {
  let pressed: EventTarget | null = null
  let justSelected: HTMLInputElement | null = null

  const onMouseDown = (event: MouseEvent) => {
    pressed = event.target
  }
  const onFocusIn = (event: FocusEvent) => {
    const field = event.target
    if (!enabled() || !selectable(field) || !field.value) return
    field.select()
    // Entered by a click: keep the selection when the button is released
    justSelected = pressed === field ? field : null
    // A field may show another text while edited (e.g. an asset's value typed, instead of the
    // value without its deducted service): select again once it changed
    const shown = field.value
    requestAnimationFrame(() => {
      if (root.activeElement === field && field.value !== shown) field.select()
    })
  }
  const onMouseUp = (event: MouseEvent) => {
    if (justSelected && event.target === justSelected) event.preventDefault()
    justSelected = null
    pressed = null
  }

  root.addEventListener('mousedown', onMouseDown, true)
  root.addEventListener('focusin', onFocusIn)
  root.addEventListener('mouseup', onMouseUp, true)
  return () => {
    root.removeEventListener('mousedown', onMouseDown, true)
    root.removeEventListener('focusin', onFocusIn)
    root.removeEventListener('mouseup', onMouseUp, true)
  }
}

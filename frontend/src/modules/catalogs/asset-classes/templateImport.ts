/**
 * Bringing the specification template of another asset class (of the same vertical) into the
 * one being edited. Fields are matched by name (case and spaces ignored). "add" appends the
 * fields this template does not have yet; "replace" takes the other template as it is, keeping
 * the identity (`key`) of fields with the same name so values already saved stay linked. New
 * fields get an empty key (the API gives them one on save).
 */
import type { SpecField } from './api'

export type ImportMode = 'add' | 'replace'

const name = (field: SpecField) => field.label.trim().toLowerCase().replace(/\s+/g, ' ')

const copy = (field: SpecField, key = ''): SpecField => ({
  ...field,
  key,
  options: [...(field.options ?? [])],
})

export function importFields(
  current: SpecField[],
  source: SpecField[],
  mode: ImportMode,
): { fields: SpecField[]; added: number; skipped: number } {
  const byName = new Map(current.map((field) => [name(field), field]))
  if (mode === 'replace') {
    const fields = source.map((field) => copy(field, byName.get(name(field))?.key ?? ''))
    return { fields, added: fields.filter((f) => !f.key).length, skipped: 0 }
  }
  const fresh = source.filter((field) => !byName.has(name(field))).map((field) => copy(field))
  return {
    fields: [...current, ...fresh],
    added: fresh.length,
    skipped: source.length - fresh.length,
  }
}

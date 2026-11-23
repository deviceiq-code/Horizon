/** Rows of the expected list editor (ExpectedItemsEditor.vue). */
import type { ExpectedItem } from './api'

export interface EditorRow extends ExpectedItem {
  /** Local key for the list */
  key: number
  /** Problems found when it was pasted (model not found, bad quantity…) */
  errors: string[]
}

let nextKey = 1

export function newKey(): number {
  return nextKey++
}

export function toRows(items: ExpectedItem[]): EditorRow[] {
  return items.map((item) => ({ ...item, key: newKey(), errors: [] }))
}

/** What the API takes (rows already checked). */
export function toInput(rows: EditorRow[]) {
  return rows.map((row) => ({
    asset_model: row.asset_model!,
    serial: row.serial,
    quantity: row.quantity ?? 1,
  }))
}

export function isInvalid(row: EditorRow): boolean {
  return (
    row.errors.length > 0 ||
    row.asset_model === null ||
    !row.quantity ||
    row.quantity < 1 ||
    (!!row.serial && row.quantity !== 1)
  )
}

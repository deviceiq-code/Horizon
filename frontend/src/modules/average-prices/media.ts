/**
 * The photo and documents of an average price as changed in its form: pending until the form is
 * saved, then applied to the row (they belong to the row, shared by every version — changing
 * them never creates a version). Cancelling the form discards them.
 */
import { ApiError } from '@/api'
import {
  deletePriceDocument,
  deletePricePhoto,
  setPhotoFromUrl,
  uploadPriceDocument,
  uploadPricePhoto,
} from './api'

/** What happens to the photo: kept, replaced by a file or by an image on the internet, removed */
export type PhotoChange =
  | null
  | { kind: 'file'; file: File; preview: string }
  | { kind: 'url'; url: string; source: string }
  | { kind: 'remove' }

export interface MediaChanges {
  photo: PhotoChange
  /** Files to attach */
  add: File[]
  /** Documents to delete (ids) */
  remove: number[]
}

/** How the price's form was saved: a new price, a new version, or only its photo and
 * documents (no version created) */
export type SaveOutcome = 'created' | 'version' | 'media'

export const noMediaChanges = (): MediaChanges => ({ photo: null, add: [], remove: [] })

export const hasMediaChanges = (changes: MediaChanges) =>
  changes.photo !== null || changes.add.length > 0 || changes.remove.length > 0

function reason(error: unknown): string {
  if (error instanceof ApiError) {
    const fields = error.fieldErrors()
    const messages = fields.file ?? fields.url
    if (messages?.length) return messages.join(' ')
    if (error.message) return error.message
  }
  return ''
}

/**
 * Apply the changes to the row, one by one; what the server refuses is reported (by file name)
 * and the rest still applied. Returns the problems, empty when all went well.
 */
export async function applyMediaChanges(rowId: number, changes: MediaChanges) {
  const problems: { name: string; reason: string }[] = []
  const photo = changes.photo
  try {
    if (photo?.kind === 'file') await uploadPricePhoto(rowId, photo.file)
    else if (photo?.kind === 'url') await setPhotoFromUrl(rowId, photo.url, photo.source)
    else if (photo?.kind === 'remove') await deletePricePhoto(rowId)
  } catch (error) {
    problems.push({ name: photo?.kind === 'file' ? photo.file.name : '', reason: reason(error) })
  }
  for (const id of changes.remove) {
    try {
      await deletePriceDocument(rowId, id)
    } catch (error) {
      problems.push({ name: '', reason: reason(error) })
    }
  }
  for (const file of changes.add) {
    try {
      await uploadPriceDocument(rowId, file)
    } catch (error) {
      problems.push({ name: file.name, reason: reason(error) })
    }
  }
  return problems
}

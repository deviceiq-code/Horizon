/**
 * Square pictures (e.g. people's photos shown in a circle): the browser crops the center of
 * the image and resizes it before sending, so the server stores a small file.
 */

/** Pixels of the stored picture: twice the 96 px it is shown at, sharp on high-density screens. */
export const SQUARE_PHOTO_SIZE = 192

export async function squareImage(file: File, size = SQUARE_PHOTO_SIZE): Promise<File> {
  const bitmap = await createImageBitmap(file)
  const side = Math.min(bitmap.width, bitmap.height)
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const context = canvas.getContext('2d')
  if (!context) throw new Error('Canvas not available')
  // White behind transparent pictures (stored as JPEG)
  context.fillStyle = '#fff'
  context.fillRect(0, 0, size, size)
  context.imageSmoothingQuality = 'high'
  context.drawImage(
    bitmap,
    (bitmap.width - side) / 2,
    (bitmap.height - side) / 2,
    side,
    side,
    0,
    0,
    size,
    size,
  )
  bitmap.close()
  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, 'image/jpeg', 0.9),
  )
  if (!blob) throw new Error('Could not encode the picture')
  const stem = file.name.replace(/\.[^.]*$/, '') || 'photo'
  return new File([blob], `${stem}.jpg`, { type: 'image/jpeg' })
}

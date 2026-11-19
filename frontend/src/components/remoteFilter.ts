/**
 * Which options a RemoteAutocomplete shows in its dropdown while the user types.
 *
 * The server already filtered its results (possibly by fields not shown, like email), so those
 * always show. Options kept only so selected chips have a title (records the latest search did
 * not return) show only if their title contains the typed text.
 */
export function showInDropdown(
  option: { value: number; title: string },
  query: string,
  latestResults: ReadonlySet<number>,
): boolean {
  const q = query.trim().toLowerCase()
  if (!q || latestResults.has(option.value)) return true
  return option.title.toLowerCase().includes(q)
}

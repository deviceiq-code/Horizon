/** Dates of appointments: typed as a local day and times, sent as ISO instants. */

const pad = (n: number) => String(n).padStart(2, '0')

/** An ISO instant → the local day ("2026-11-24") and time ("08:30"). */
export function localParts(iso: string): { date: string; time: string } {
  const d = new Date(iso)
  return {
    date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
    time: `${pad(d.getHours())}:${pad(d.getMinutes())}`,
  }
}

/** A local day and time → the ISO instant. */
export function toIso(date: string, time: string): string {
  return new Date(`${date}T${time || '00:00'}`).toISOString()
}

/** The local day ("2026-11-24") of a Date. */
export function dayOf(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const d = new Date(value.replace(" ", "T"))
  return Number.isNaN(d.getTime()) ? null : d
}

export function formatDuration(totalSeconds: number | null | undefined): string {
  const s = Math.max(0, Math.round(totalSeconds ?? 0))
  if (s < 60) return `${s}s`
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (h === 0) return `${m}m ${String(s % 60).padStart(2, "0")}s`
  return `${h}h ${String(m).padStart(2, "0")}m`
}

export function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const pad = (n: number) => String(n).padStart(2, "0")
  return h > 0 ? `${h}:${pad(m)}:${pad(sec)}` : `${pad(m)}:${pad(sec)}`
}

const dateFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" })
const timeFmt = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" })

export function formatDate(value: string | null | undefined): string {
  const d = parseDate(value)
  return d ? dateFmt.format(d) : "—"
}

export function formatTime(value: string | null | undefined): string {
  const d = parseDate(value)
  return d ? timeFmt.format(d) : "—"
}

/** "HH:MM:SS" (time only) -> localized short time */
export function formatClockTime(value: string | null | undefined): string {
  if (!value) return "—"
  const [h, m, s] = value.split(":").map(Number)
  const d = new Date()
  d.setHours(h, m, s || 0)
  return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit", second: "2-digit" }).format(d)
}

const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" })

export function formatRelative(value: string | null | undefined): string {
  const d = parseDate(value)
  if (!d) return "—"
  const diff = (d.getTime() - Date.now()) / 1000
  const abs = Math.abs(diff)
  if (abs < 60) return "just now"
  if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute")
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour")
  if (abs < 86400 * 7) return rtf.format(Math.round(diff / 86400), "day")
  return formatDate(value)
}

export function sessionSeconds(start: string | null, end: string | null): number {
  const a = parseDate(start)
  const b = end ? parseDate(end) : new Date()
  if (!a || !b) return 0
  return Math.max(0, (b.getTime() - a.getTime()) / 1000)
}

export function initials(name: string): string {
  return name
    .replace(/^(prof|dr|mr|mrs|ms)\.?\s+/i, "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join("")
}

export function greeting(): string {
  const h = new Date().getHours()
  if (h < 12) return "Good morning"
  if (h < 17) return "Good afternoon"
  return "Good evening"
}

export function sessionTitle(s: { subject_name: string | null; classroom_name: string | null }): string {
  return s.subject_name ?? "General session"
}

export type SessionStatus = "Ongoing" | "Ended"
export type AttendanceStatus = "Present" | "Late" | "Early Leave" | "Absent"

export type SessionRow = {
  id: number
  classroom_id: number | null
  camera_id: number | null
  subject_id: number | null
  teacher_id: number | null
  start_time: string | null
  end_time: string | null
  status: SessionStatus
  classroom_name: string | null
  subject_name: string | null
  teacher_name: string | null
  camera_name: string | null
  attendees: number
  present_count: number
  late_count: number
  early_count: number
}

export type Camera = {
  id: number
  name: string
  position: string | null
  url: string | null
  status: string | null
  type: string
}

export type Classroom = {
  id: number
  name: string
  cameras: Camera[]
  total_sessions: number
}

export type Subject = { id: number; name: string; students?: number; sessions?: number }

export type Teacher = {
  id: number
  name: string
  photo: string | null
  has_face: number
  sessions?: number
}

export type Student = {
  student_id: string
  name: string
  photo: string | null
  courses: string[]
  course_ids: number[]
  sessions_attended: number
  last_seen: string | null
}

export type Overview = {
  stats: {
    students: number
    teachers: number
    subjects: number
    classrooms: number
    cameras: number
    live_sessions: number
    total_sessions: number
    attendance_records: number
    status_breakdown: Partial<Record<AttendanceStatus, number>>
  }
  recent_sessions: SessionRow[]
  classrooms: Classroom[]
  subjects: Subject[]
  teachers: Teacher[]
}

export type LivePerson = {
  id: string
  name: string
  type: "student" | "teacher"
  photo: string | null
  face_image: string
  first_seen: string
  last_seen: string
  duration: number
  present: boolean
}

export type LiveStatus = {
  people: LivePerson[]
  present_count: number
  seen_count: number
  faces_in_view: number
}

export type ReportLog = {
  id: string
  name: string
  photo: string | null
  type: "student" | "teacher"
  first_seen: string | null
  last_seen: string | null
  duration: number
  status: AttendanceStatus
}

export type Report = { session: SessionRow; logs: ReportLog[] }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
  })
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    throw new Error(data?.error ?? `Request failed (${res.status})`)
  }
  return data as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T = unknown>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) }),
  patch: <T = unknown>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  del: <T = unknown>(path: string) => request<T>(path, { method: "DELETE" }),
}

/** Tell listeners (e.g. the sidebar's live badge) that sessions changed. */
export const SESSIONS_CHANGED = "sessions-changed"
export function notifySessionsChanged() {
  window.dispatchEvent(new Event(SESSIONS_CHANGED))
}

import { useEffect, useMemo } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import {
  ArrowLeftIcon,
  CalendarIcon,
  ClockIcon,
  DownloadIcon,
  PrinterIcon,
  SchoolIcon,
  UserIcon,
  UsersIcon,
} from "lucide-react"

import { PersonAvatar } from "@/components/person-avatar"
import { StatusBadge } from "@/components/status-badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useApi } from "@/hooks/use-api"
import type { Report } from "@/lib/api"
import { formatClockTime, formatDate, formatDuration, formatTime, sessionSeconds, sessionTitle } from "@/lib/format"
import { cn } from "@/lib/utils"

const SUMMARY = [
  { key: "Present", label: "Present", color: "text-emerald-600 dark:text-emerald-400", bar: "bg-emerald-500" },
  { key: "Late", label: "Late", color: "text-amber-600 dark:text-amber-400", bar: "bg-amber-500" },
  { key: "Early Leave", label: "Left early", color: "text-orange-600 dark:text-orange-400", bar: "bg-orange-500" },
  { key: "Absent", label: "Absent", color: "text-rose-600 dark:text-rose-400", bar: "bg-rose-500" },
] as const

function downloadCsv(report: Report) {
  const header = ["ID", "Name", "Role", "Status", "First seen", "Last seen", "Duration (s)"]
  const lines = report.logs.map((l) =>
    [l.id, l.name, l.type, l.status, l.first_seen ?? "", l.last_seen ?? "", l.duration]
      .map((v) => `"${String(v).replace(/"/g, '""')}"`)
      .join(",")
  )
  const blob = new Blob([[header.join(","), ...lines].join("\n")], { type: "text/csv" })
  const a = document.createElement("a")
  a.href = URL.createObjectURL(blob)
  const s = report.session
  a.download = `attendance-session-${s.id}-${(s.start_time ?? "").slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(a.href)
}

export default function ReportPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { data, loading, error } = useApi<Report>(`/api/sessions/${id}/report`)

  useEffect(() => {
    if (data?.session.status === "Ongoing") navigate(`/live/${id}`, { replace: true })
  }, [data, id, navigate])

  const students = useMemo(() => data?.logs.filter((l) => l.type === "student") ?? [], [data])
  const counts = useMemo(() => {
    const c: Record<string, number> = {}
    for (const l of students) c[l.status] = (c[l.status] ?? 0) + 1
    return c
  }, [students])
  const attended = students.length - (counts.Absent ?? 0)
  const rate = students.length ? Math.round((attended / students.length) * 100) : 0

  if (error) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>Report not found</EmptyTitle>
          <EmptyDescription>{error}</EmptyDescription>
        </EmptyHeader>
        <Button asChild variant="outline">
          <Link to="/sessions">Back to sessions</Link>
        </Button>
      </Empty>
    )
  }

  const s = data?.session

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <Button asChild variant="ghost" size="icon" className="mt-0.5 shrink-0 print:hidden">
            <Link to="/sessions" aria-label="Back">
              <ArrowLeftIcon />
            </Link>
          </Button>
          <div className="min-w-0 space-y-2">
            <div className="text-xs font-medium text-muted-foreground">Attendance report · Session #{id}</div>
            {s ? (
              <h1 className="text-2xl font-semibold tracking-tight">{sessionTitle(s)}</h1>
            ) : (
              <Skeleton className="h-8 w-64" />
            )}
            {s ? (
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
                <span className="inline-flex items-center gap-1.5"><SchoolIcon className="size-4" />{s.classroom_name ?? "—"}</span>
                <span className="inline-flex items-center gap-1.5"><UserIcon className="size-4" />{s.teacher_name ?? "No teacher"}</span>
                <span className="inline-flex items-center gap-1.5"><CalendarIcon className="size-4" />{formatDate(s.start_time)}</span>
                <span className="inline-flex items-center gap-1.5">
                  <ClockIcon className="size-4" />
                  {formatTime(s.start_time)} – {formatTime(s.end_time)} ({formatDuration(sessionSeconds(s.start_time, s.end_time))})
                </span>
              </div>
            ) : null}
          </div>
        </div>
        <div className="flex gap-2 print:hidden">
          <Button variant="outline" onClick={() => window.print()} disabled={!data}>
            <PrinterIcon /> Print
          </Button>
          <Button onClick={() => data && downloadCsv(data)} disabled={!data?.logs.length}>
            <DownloadIcon /> Export CSV
          </Button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Card className="gap-0 p-5 lg:col-span-1">
          <span className="text-sm font-medium text-muted-foreground">Attendance rate</span>
          {loading ? <Skeleton className="mt-3 h-8 w-16" /> : (
            <div className="mt-2 text-3xl font-semibold tracking-tight tabular">{students.length ? `${rate}%` : "—"}</div>
          )}
          <div className="mt-1 text-xs text-muted-foreground">{attended} of {students.length} students</div>
        </Card>
        {SUMMARY.map((item) => (
          <Card key={item.key} className="gap-0 p-5">
            <span className="text-sm font-medium text-muted-foreground">{item.label}</span>
            {loading ? <Skeleton className="mt-3 h-8 w-10" /> : (
              <div className={cn("mt-2 text-3xl font-semibold tracking-tight tabular", item.color)}>{counts[item.key] ?? 0}</div>
            )}
            <div className="mt-3 h-1 overflow-hidden rounded-full bg-muted">
              <div
                className={cn("h-full rounded-full transition-all duration-700", item.bar)}
                style={{ width: `${students.length ? ((counts[item.key] ?? 0) / students.length) * 100 : 0}%` }}
              />
            </div>
          </Card>
        ))}
      </div>

      <Card className="pb-0">
        <CardHeader>
          <CardTitle>Attendance</CardTitle>
          <CardDescription>
            Late = first seen more than 25 min after start · Left early = last seen more than 5 min before the end
          </CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          {loading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
            </div>
          ) : data?.logs.length ? (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="pl-4">Person</TableHead>
                  <TableHead className="hidden sm:table-cell">First seen</TableHead>
                  <TableHead className="hidden sm:table-cell">Last seen</TableHead>
                  <TableHead className="text-right">Time in view</TableHead>
                  <TableHead className="pr-4 text-right">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.logs.map((l) => (
                  <TableRow key={`${l.type}-${l.id}`}>
                    <TableCell className="pl-4">
                      <div className="flex items-center gap-3">
                        <PersonAvatar name={l.name} src={l.photo} />
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5 font-medium">
                            {l.name}
                            {l.type === "teacher" ? (
                              <span className="rounded bg-amber-500/10 px-1.5 text-[10px] font-semibold text-amber-600 dark:text-amber-400">TEACHER</span>
                            ) : null}
                          </div>
                          <div className="font-mono text-xs text-muted-foreground">{l.type === "student" ? l.id : `T-${l.id}`}</div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="hidden text-muted-foreground tabular sm:table-cell">{formatClockTime(l.first_seen)}</TableCell>
                    <TableCell className="hidden text-muted-foreground tabular sm:table-cell">{formatClockTime(l.last_seen)}</TableCell>
                    <TableCell className="text-right tabular">{l.status === "Absent" ? "—" : formatDuration(l.duration)}</TableCell>
                    <TableCell className="pr-4 text-right"><StatusBadge status={l.status} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon"><UsersIcon /></EmptyMedia>
                <EmptyTitle>No one was recorded</EmptyTitle>
                <EmptyDescription>No enrolled faces were recognised during this session.</EmptyDescription>
              </EmptyHeader>
            </Empty>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

import { Link, useNavigate } from "react-router-dom"
import {
  ArrowRightIcon,
  CalendarCheckIcon,
  CctvIcon,
  CheckCircle2Icon,
  GraduationCapIcon,
  RadioIcon,
  SchoolIcon,
} from "lucide-react"

import { PageHeader } from "@/components/page-header"
import { StartSessionDialog } from "@/components/start-session-dialog"
import { StatCard } from "@/components/stat-card"
import { STATUS_COLORS, StatusBadge } from "@/components/status-badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useApi } from "@/hooks/use-api"
import type { AttendanceStatus, Overview } from "@/lib/api"
import { formatDate, formatDuration, formatTime, greeting, sessionSeconds, sessionTitle } from "@/lib/format"

const BREAKDOWN: AttendanceStatus[] = ["Present", "Late", "Early Leave"]

export default function DashboardPage() {
  const navigate = useNavigate()
  const { data, loading } = useApi<Overview>("/api/overview", { interval: 15000 })
  const stats = data?.stats
  const breakdown = stats?.status_breakdown ?? {}
  const records = stats?.attendance_records ?? 0
  const onTime = records ? Math.round(((breakdown.Present ?? 0) / records) * 100) : 0
  const live = data?.recent_sessions.filter((s) => s.status === "Ongoing") ?? []

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={new Intl.DateTimeFormat(undefined, { weekday: "long", month: "long", day: "numeric" }).format(new Date())}
        title={greeting()}
        description="Here's what's happening across your classrooms today."
      />

      {live.length > 0 ? (
        <div className="flex flex-col gap-3 rounded-xl bg-primary/[0.06] p-4 ring-1 ring-primary/15 sm:flex-row sm:items-center">
          <span className="relative flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
            <RadioIcon className="size-4" />
            <span className="absolute inset-0 animate-ping rounded-full bg-primary/20" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium">
              {live.length === 1 ? "A session is live right now" : `${live.length} sessions are live right now`}
            </div>
            <div className="truncate text-sm text-muted-foreground">
              {live.map((s) => `${sessionTitle(s)} · ${s.classroom_name ?? "Classroom"}`).join("  •  ")}
            </div>
          </div>
          <Button asChild variant="outline" className="shrink-0">
            <Link to={live.length === 1 ? `/live/${live[0].id}` : "/live"}>
              Open live view <ArrowRightIcon />
            </Link>
          </Button>
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <StatCard
          label="Enrolled students"
          value={stats?.students ?? 0}
          hint={`${stats?.teachers ?? 0} teachers · ${stats?.subjects ?? 0} subjects`}
          icon={GraduationCapIcon}
          loading={loading}
        />
        <StatCard
          label="Sessions held"
          value={stats?.total_sessions ?? 0}
          hint={stats?.live_sessions ? `${stats.live_sessions} live now` : "None live right now"}
          icon={CalendarCheckIcon}
          loading={loading}
        />
        <StatCard
          label="On-time rate"
          value={records ? `${onTime}%` : "—"}
          hint={`${records} attendance records`}
          icon={CheckCircle2Icon}
          loading={loading}
          accent="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
        />
        <StatCard
          label="Classrooms"
          value={stats?.classrooms ?? 0}
          hint={`${stats?.cameras ?? 0} camera${stats?.cameras === 1 ? "" : "s"} connected`}
          icon={SchoolIcon}
          loading={loading}
        />
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Recent sessions</CardTitle>
            <CardDescription>Select a session to open its attendance report.</CardDescription>
            <CardAction>
              <Button asChild variant="ghost" size="sm">
                <Link to="/sessions">
                  View all <ArrowRightIcon />
                </Link>
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent className="px-0">
            {loading ? (
              <div className="space-y-2 px-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : data && data.recent_sessions.length ? (
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="pl-4">Session</TableHead>
                    <TableHead className="hidden md:table-cell">When</TableHead>
                    <TableHead className="text-right">Attendance</TableHead>
                    <TableHead className="pr-4 text-right">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.recent_sessions.map((s) => (
                    <TableRow
                      key={s.id}
                      className="cursor-pointer"
                      onClick={() => navigate(s.status === "Ongoing" ? `/live/${s.id}` : `/sessions/${s.id}`)}
                    >
                      <TableCell className="pl-4">
                        <div className="font-medium">{sessionTitle(s)}</div>
                        <div className="text-xs text-muted-foreground">
                          {s.classroom_name ?? "Deleted classroom"}
                          {s.teacher_name ? ` · ${s.teacher_name}` : ""}
                        </div>
                      </TableCell>
                      <TableCell className="hidden text-muted-foreground md:table-cell">
                        <div>{formatDate(s.start_time)}</div>
                        <div className="text-xs">
                          {formatTime(s.start_time)} · {formatDuration(sessionSeconds(s.start_time, s.end_time))}
                        </div>
                      </TableCell>
                      <TableCell className="text-right tabular">
                        {s.status === "Ongoing" ? (
                          <span className="text-muted-foreground">In progress</span>
                        ) : (
                          <span className="font-medium">{s.attendees}</span>
                        )}
                      </TableCell>
                      <TableCell className="pr-4 text-right">
                        <StatusBadge status={s.status} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <Empty className="border-0">
                <EmptyHeader>
                  <EmptyMedia variant="icon">
                    <CalendarCheckIcon />
                  </EmptyMedia>
                  <EmptyTitle>No sessions yet</EmptyTitle>
                  <EmptyDescription>Start a session and the cameras will take attendance automatically.</EmptyDescription>
                </EmptyHeader>
                <EmptyContent>
                  <StartSessionDialog />
                </EmptyContent>
              </Empty>
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Attendance breakdown</CardTitle>
              <CardDescription>All recorded check-ins</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex h-2.5 overflow-hidden rounded-full bg-muted">
                {BREAKDOWN.map((k) =>
                  breakdown[k] ? (
                    <div
                      key={k}
                      className={`${STATUS_COLORS[k]} transition-all duration-700`}
                      style={{ width: `${((breakdown[k] ?? 0) / records) * 100}%` }}
                    />
                  ) : null
                )}
              </div>
              <ul className="space-y-2.5">
                {BREAKDOWN.map((k) => (
                  <li key={k} className="flex items-center gap-2 text-sm">
                    <span className={`size-2 rounded-full ${STATUS_COLORS[k]}`} />
                    <span className="text-muted-foreground">{k}</span>
                    <span className="ml-auto font-medium tabular">{breakdown[k] ?? 0}</span>
                    <span className="w-10 text-right text-xs text-muted-foreground tabular">
                      {records ? `${Math.round(((breakdown[k] ?? 0) / records) * 100)}%` : "—"}
                    </span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Classrooms</CardTitle>
              <CardDescription>Camera readiness</CardDescription>
              <CardAction>
                <Button asChild variant="ghost" size="sm">
                  <Link to="/classrooms">
                    Manage <ArrowRightIcon />
                  </Link>
                </Button>
              </CardAction>
            </CardHeader>
            <CardContent>
              {loading ? (
                <Skeleton className="h-24 w-full" />
              ) : (
                <ul className="divide-y">
                  {[...(data?.classrooms ?? [])]
                    .sort((a, b) => b.cameras.length - a.cameras.length)
                    .slice(0, 5)
                    .map((c) => (
                      <li key={c.id} className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0">
                        <span className="flex size-8 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                          <CctvIcon className="size-4" />
                        </span>
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-medium">{c.name}</div>
                          <div className="text-xs text-muted-foreground">
                            {c.cameras.length ? `${c.cameras.length} camera${c.cameras.length > 1 ? "s" : ""}` : "No cameras"}
                          </div>
                        </div>
                        <span
                          className={`size-2 rounded-full ${c.cameras.length ? "bg-emerald-500" : "bg-muted-foreground/30"}`}
                          title={c.cameras.length ? "Ready" : "Needs a camera"}
                        />
                      </li>
                    ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

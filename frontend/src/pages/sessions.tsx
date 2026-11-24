import { useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { HistoryIcon, SearchIcon } from "lucide-react"

import { PageHeader } from "@/components/page-header"
import { StatusBadge } from "@/components/status-badge"
import { Card } from "@/components/ui/card"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useApi } from "@/hooks/use-api"
import type { SessionRow } from "@/lib/api"
import { formatDate, formatDuration, formatTime, sessionSeconds, sessionTitle } from "@/lib/format"

function AttendanceBar({ s }: { s: SessionRow }) {
  const total = s.attendees || 1
  return (
    <div className="flex items-center justify-end gap-3">
      <div className="hidden h-1.5 w-20 overflow-hidden rounded-full bg-muted sm:flex">
        <div className="bg-emerald-500" style={{ width: `${(s.present_count / total) * 100}%` }} />
        <div className="bg-amber-500" style={{ width: `${(s.late_count / total) * 100}%` }} />
        <div className="bg-orange-500" style={{ width: `${(s.early_count / total) * 100}%` }} />
      </div>
      <span className="w-6 text-right font-medium tabular">{s.attendees}</span>
    </div>
  )
}

export default function SessionsPage() {
  const navigate = useNavigate()
  const { data, loading } = useApi<SessionRow[]>("/api/sessions", { interval: 15000 })
  const [filter, setFilter] = useState("all")
  const [query, setQuery] = useState("")

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (data ?? []).filter((s) => {
      if (filter === "live" && s.status !== "Ongoing") return false
      if (filter === "ended" && s.status !== "Ended") return false
      if (!q) return true
      return [s.subject_name, s.classroom_name, s.teacher_name, `#${s.id}`].some((v) => v?.toLowerCase().includes(q))
    })
  }, [data, filter, query])

  return (
    <div className="space-y-6">
      <PageHeader
        title="Session history"
        description="Every class session and the attendance it recorded."
      />
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Tabs value={filter} onValueChange={setFilter}>
          <TabsList>
            <TabsTrigger value="all">All</TabsTrigger>
            <TabsTrigger value="live">Live</TabsTrigger>
            <TabsTrigger value="ended">Completed</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="relative sm:w-72">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search subject, classroom, teacher…"
            className="pl-8"
          />
        </div>
      </div>
      <Card className="py-0">
        {loading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : rows.length ? (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="pl-4">Session</TableHead>
                <TableHead className="hidden md:table-cell">Classroom</TableHead>
                <TableHead className="hidden lg:table-cell">Teacher</TableHead>
                <TableHead className="hidden sm:table-cell">Date</TableHead>
                <TableHead className="hidden sm:table-cell">Duration</TableHead>
                <TableHead className="text-right">Attendees</TableHead>
                <TableHead className="pr-4 text-right">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((s) => (
                <TableRow
                  key={s.id}
                  className="cursor-pointer"
                  onClick={() => navigate(s.status === "Ongoing" ? `/live/${s.id}` : `/sessions/${s.id}`)}
                >
                  <TableCell className="pl-4">
                    <div className="font-medium">{sessionTitle(s)}</div>
                    <div className="text-xs text-muted-foreground">#{s.id}<span className="sm:hidden"> · {formatDate(s.start_time)}</span></div>
                  </TableCell>
                  <TableCell className="hidden md:table-cell">{s.classroom_name ?? "—"}</TableCell>
                  <TableCell className="hidden text-muted-foreground lg:table-cell">{s.teacher_name ?? "—"}</TableCell>
                  <TableCell className="hidden sm:table-cell">
                    <div>{formatDate(s.start_time)}</div>
                    <div className="text-xs text-muted-foreground">{formatTime(s.start_time)}</div>
                  </TableCell>
                  <TableCell className="hidden text-muted-foreground tabular sm:table-cell">
                    {formatDuration(sessionSeconds(s.start_time, s.end_time))}
                  </TableCell>
                  <TableCell className="text-right">
                    {s.status === "Ongoing" ? <span className="text-muted-foreground">—</span> : <AttendanceBar s={s} />}
                  </TableCell>
                  <TableCell className="pr-4 text-right">
                    <StatusBadge status={s.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <HistoryIcon />
              </EmptyMedia>
              <EmptyTitle>{data?.length ? "No matching sessions" : "No sessions yet"}</EmptyTitle>
              <EmptyDescription>
                {data?.length ? "Try a different search or filter." : "Sessions you run will be listed here."}
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
      </Card>
    </div>
  )
}

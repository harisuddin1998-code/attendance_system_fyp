import { useEffect, useRef, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { toast } from "sonner"
import {
  ArrowLeftIcon,
  CameraOffIcon,
  EyeIcon,
  RefreshCwIcon,
  ScanFaceIcon,
  SquareIcon,
  UserCheckIcon,
  UsersIcon,
} from "lucide-react"

import { ConfirmDialog } from "@/components/confirm-dialog"
import { PersonAvatar } from "@/components/person-avatar"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { useApi } from "@/hooks/use-api"
import { api, notifySessionsChanged, type Camera, type LiveStatus, type SessionRow } from "@/lib/api"
import { formatClock, formatClockTime, formatDuration, sessionSeconds, sessionTitle } from "@/lib/format"
import { cn } from "@/lib/utils"

const POSITION_LABEL: Record<string, string> = { door: "Door", cctv1: "CCTV 1", cctv2: "CCTV 2" }

function CameraFeed({ sessionId, camera }: { sessionId: number; camera: Camera }) {
  const imgRef = useRef<HTMLImageElement>(null)
  const [nonce, setNonce] = useState(() => Date.now())
  const [state, setState] = useState<"loading" | "live" | "error">("loading")

  // Close the MJPEG connection when leaving the page (browsers limit open connections per host).
  useEffect(() => {
    const img = imgRef.current
    return () => {
      if (img) img.src = ""
    }
  }, [])

  return (
    <div className="group relative aspect-video overflow-hidden rounded-xl bg-zinc-950 ring-1 ring-foreground/10">
      {state === "loading" ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-sm text-zinc-400">
          <span className="size-6 animate-spin rounded-full border-2 border-zinc-600 border-t-zinc-200" />
          Connecting to camera…
        </div>
      ) : null}
      {state === "error" ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-sm text-zinc-400">
          <CameraOffIcon className="size-6" />
          Camera unavailable
          <Button
            size="sm"
            variant="secondary"
            onClick={() => {
              setState("loading")
              setNonce(Date.now())
            }}
          >
            <RefreshCwIcon /> Retry
          </Button>
        </div>
      ) : null}
      <img
        ref={imgRef}
        src={`/video_feed/${sessionId}/${camera.id}?t=${nonce}`}
        alt={camera.name}
        onLoad={() => setState("live")}
        onError={() => setState("error")}
        className={cn("size-full object-contain transition-opacity duration-500", state === "live" ? "opacity-100" : "opacity-0")}
      />
      <div className="absolute inset-x-0 top-0 flex items-center justify-between bg-gradient-to-b from-black/60 to-transparent p-3">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-black/40 px-2.5 py-1 text-xs font-medium text-white backdrop-blur">
          <span className={cn("size-1.5 rounded-full", state === "live" ? "animate-pulse bg-red-500" : "bg-zinc-400")} />
          {state === "live" ? "LIVE" : "OFFLINE"}
        </span>
        <span className="rounded-full bg-black/40 px-2.5 py-1 text-xs font-medium text-white backdrop-blur">
          {POSITION_LABEL[camera.position ?? ""] ?? camera.name}
        </span>
      </div>
    </div>
  )
}

function MiniStat({ icon: Icon, label, value }: { icon: typeof UsersIcon; label: string; value: number | string }) {
  return (
    <div className="rounded-lg bg-muted/60 p-3">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Icon className="size-3.5" /> {label}
      </div>
      <div className="mt-1 text-2xl font-semibold tabular">{value}</div>
    </div>
  )
}

export default function LiveSessionPage() {
  const { id } = useParams()
  const sessionId = Number(id)
  const navigate = useNavigate()
  const { data, error } = useApi<{ session: SessionRow; cameras: Camera[] }>(`/api/sessions/${sessionId}`)
  const { data: live } = useApi<LiveStatus>(`/api/live_status/${sessionId}`, { interval: 2000 })
  const [, setTick] = useState(0)

  useEffect(() => {
    const t = window.setInterval(() => setTick((n) => n + 1), 1000)
    return () => window.clearInterval(t)
  }, [])

  useEffect(() => {
    if (data?.session.status === "Ended") navigate(`/sessions/${sessionId}`, { replace: true })
  }, [data, navigate, sessionId])

  async function endSession() {
    try {
      await api.post(`/api/sessions/${sessionId}/end`)
      notifySessionsChanged()
      toast.success("Attendance saved", { description: `${live?.seen_count ?? 0} people recorded for this session.` })
      navigate(`/sessions/${sessionId}`)
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  if (error) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>Session not found</EmptyTitle>
          <EmptyDescription>{error}</EmptyDescription>
        </EmptyHeader>
        <Button asChild variant="outline">
          <Link to="/live">Back to live sessions</Link>
        </Button>
      </Empty>
    )
  }

  const session = data?.session
  const cameras = data?.cameras ?? []
  const people = live?.people ?? []

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <Button asChild variant="ghost" size="icon" className="shrink-0">
            <Link to="/live" aria-label="Back">
              <ArrowLeftIcon />
            </Link>
          </Button>
          <div className="min-w-0">
            {session ? (
              <>
                <h1 className="truncate text-xl font-semibold tracking-tight">{sessionTitle(session)}</h1>
                <p className="truncate text-sm text-muted-foreground">
                  {session.classroom_name}
                  {session.teacher_name ? ` · ${session.teacher_name}` : ""}
                </p>
              </>
            ) : (
              <>
                <Skeleton className="h-6 w-48" />
                <Skeleton className="mt-1.5 h-4 w-32" />
              </>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-lg bg-muted px-3 py-1.5">
            <span className="size-2 animate-pulse rounded-full bg-red-500" />
            <span className="font-mono text-sm font-medium tabular">
              {session ? formatClock(sessionSeconds(session.start_time, null)) : "--:--"}
            </span>
          </div>
          <ConfirmDialog
            trigger={
              <Button variant="destructive" disabled={!session}>
                <SquareIcon className="fill-current" /> End session
              </Button>
            }
            title="End this session?"
            description={`Attendance will be finalised for the ${live?.seen_count ?? 0} people recognised so far, and the cameras will stop recording for this session.`}
            confirmLabel="End & save attendance"
            destructive
            onConfirm={endSession}
          />
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className={cn("grid content-start gap-4", cameras.length > 1 && "md:grid-cols-2")}>
          {!data
            ? <Skeleton className="aspect-video rounded-xl" />
            : cameras.length
              ? cameras.map((c) => <CameraFeed key={c.id} sessionId={sessionId} camera={c} />)
              : (
                <Card>
                  <Empty>
                    <EmptyHeader>
                      <EmptyMedia variant="icon"><CameraOffIcon /></EmptyMedia>
                      <EmptyTitle>No cameras in this classroom</EmptyTitle>
                      <EmptyDescription>Add a camera on the Classrooms page to record attendance.</EmptyDescription>
                    </EmptyHeader>
                  </Empty>
                </Card>
              )}
          <p className="flex items-center gap-2 text-xs text-muted-foreground md:col-span-full">
            <ScanFaceIcon className="size-3.5" />
            Faces are recognised every couple of seconds.
            <span className="inline-flex items-center gap-1"><span className="size-2 rounded-sm bg-emerald-500" /> student</span>
            <span className="inline-flex items-center gap-1"><span className="size-2 rounded-sm bg-amber-500" /> teacher</span>
            <span className="inline-flex items-center gap-1"><span className="size-2 rounded-sm bg-red-500" /> unknown</span>
          </p>
        </div>

        <Card className="h-fit xl:sticky xl:top-20">
          <CardHeader>
            <CardTitle>In this session</CardTitle>
            <CardDescription>Updates live as people are recognised</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-2">
              <MiniStat icon={EyeIcon} label="In view" value={live?.present_count ?? 0} />
              <MiniStat icon={UserCheckIcon} label="Recognised" value={live?.seen_count ?? 0} />
              <MiniStat icon={ScanFaceIcon} label="Faces" value={live?.faces_in_view ?? 0} />
            </div>
            {people.length ? (
              <div className="-mx-2 max-h-[min(56vh,520px)] overflow-y-auto">
                <ul className="space-y-1 px-2">
                  {people.map((p) => (
                    <li
                      key={p.id}
                      className={cn(
                        "flex items-center gap-3 rounded-lg p-2 transition-colors animate-in fade-in-0 slide-in-from-top-1 hover:bg-muted/60",
                        !p.present && "opacity-60"
                      )}
                    >
                      <div className="relative">
                        <PersonAvatar name={p.name} src={p.photo || p.face_image} />
                        <span
                          className={cn(
                            "absolute -right-0.5 -bottom-0.5 size-3 rounded-full ring-2 ring-card",
                            p.present ? "bg-emerald-500" : "bg-muted-foreground/40"
                          )}
                        />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5 truncate text-sm font-medium">
                          {p.name}
                          {p.type === "teacher" ? (
                            <span className="rounded bg-amber-500/10 px-1.5 text-[10px] font-semibold text-amber-600 dark:text-amber-400">
                              TEACHER
                            </span>
                          ) : null}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          Since {formatClockTime(p.first_seen)} · {p.present ? "in view" : `last seen ${formatClockTime(p.last_seen)}`}
                        </div>
                      </div>
                      <span className="text-xs font-medium text-muted-foreground tabular">{formatDuration(p.duration)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed py-10 text-center">
                <span className="relative flex size-10 items-center justify-center rounded-full bg-muted">
                  <ScanFaceIcon className="size-5 text-muted-foreground" />
                </span>
                <div className="text-sm font-medium">Looking for faces…</div>
                <div className="max-w-56 text-xs text-muted-foreground">
                  Recognised students and teachers will appear here automatically.
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

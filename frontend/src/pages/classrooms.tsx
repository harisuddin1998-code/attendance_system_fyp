import { useState } from "react"
import { toast } from "sonner"
import { CctvIcon, FilmIcon, Loader2Icon, PlayIcon, PlusIcon, SchoolIcon, Trash2Icon, WebcamIcon, WifiIcon } from "lucide-react"

import { ConfirmDialog } from "@/components/confirm-dialog"
import { PageHeader } from "@/components/page-header"
import { StartSessionDialog } from "@/components/start-session-dialog"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { useApi } from "@/hooks/use-api"
import { api, type Camera, type Classroom } from "@/lib/api"

const POSITIONS: Record<string, string> = { door: "Door", cctv1: "CCTV 1", cctv2: "CCTV 2" }

function describeSource(url: string | null) {
  const v = url ?? ""
  if (/^\d+$/.test(v)) return { icon: WebcamIcon, kind: "Webcam", detail: `Device ${v}` }
  if (/\.(mp4|avi|mov|mkv|webm)$/i.test(v)) return { icon: FilmIcon, kind: "Recorded video", detail: v.split(/[\\/]/).pop() ?? v }
  return { icon: WifiIcon, kind: "Network camera", detail: v.replace(/^\w+:\/\/([^@]*@)?/, "") }
}

function CameraRow({ camera }: { camera: Camera }) {
  const src = describeSource(camera.url)
  return (
    <li className="flex items-center gap-3 rounded-lg bg-muted/50 px-3 py-2.5">
      <src.icon className="size-4 shrink-0 text-muted-foreground" />
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium">{POSITIONS[camera.position ?? ""] ?? camera.name}</div>
        <div className="truncate font-mono text-xs text-muted-foreground" title={camera.url ?? ""}>
          {src.kind} · {src.detail}
        </div>
      </div>
      <span
        className={`size-2 shrink-0 rounded-full ${camera.status === "active" ? "bg-emerald-500" : "bg-muted-foreground/40"}`}
        title={camera.status ?? ""}
      />
    </li>
  )
}

function AddClassroomDialog({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ name: "", door: "", cctv1: "", cctv2: "" })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function save() {
    setBusy(true)
    setError(null)
    try {
      await api.post("/api/classrooms", form)
      toast.success(`${form.name.trim()} created`)
      setOpen(false)
      setForm({ name: "", door: "", cctv1: "", cctv2: "" })
      onCreated()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !busy && setOpen(o)}>
      <DialogTrigger asChild>
        <Button><PlusIcon /> Add classroom</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Add a classroom</DialogTitle>
          <DialogDescription>Connect at least one camera. Recognition runs on every camera during a session.</DialogDescription>
        </DialogHeader>
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="cname">Classroom name</FieldLabel>
            <Input id="cname" value={form.name} onChange={set("name")} placeholder="e.g. Room 204" autoFocus />
          </Field>
          {(["door", "cctv1", "cctv2"] as const).map((k) => (
            <Field key={k}>
              <FieldLabel htmlFor={k}>
                {POSITIONS[k]} camera <span className="font-normal text-muted-foreground">(optional)</span>
              </FieldLabel>
              <Input id={k} value={form[k]} onChange={set(k)} placeholder={k === "door" ? "192.168.1.20:4747" : k === "cctv1" ? "0" : "rtsp://user:pass@192.168.1.30:554/stream"} className="font-mono text-sm" />
            </Field>
          ))}
          <FieldDescription>
            Use <code className="rounded bg-muted px-1">0</code> for this computer's webcam, <code className="rounded bg-muted px-1">IP:port</code> for a phone camera app (DroidCam / IP Webcam), a full <code className="rounded bg-muted px-1">rtsp://</code> URL, or a path to a video file.
          </FieldDescription>
          {error ? <FieldError>{error}</FieldError> : null}
        </FieldGroup>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} disabled={busy}>Cancel</Button>
          <Button onClick={save} disabled={busy || !form.name.trim() || !(form.door || form.cctv1 || form.cctv2)}>
            {busy ? <Loader2Icon className="animate-spin" /> : <PlusIcon />} Create classroom
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function ClassroomsPage() {
  const { data, loading, reload } = useApi<Classroom[]>("/api/classrooms")

  async function remove(c: Classroom) {
    try {
      await api.del(`/api/classrooms/${c.id}`)
      toast.success(`${c.name} deleted`)
      reload()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  const sorted = [...(data ?? [])].sort((a, b) => b.cameras.length - a.cameras.length || a.name.localeCompare(b.name))

  return (
    <div className="space-y-6">
      <PageHeader
        title="Classrooms"
        description="Rooms and the cameras that watch them. A classroom needs at least one active camera to run a session."
        actions={<AddClassroomDialog onCreated={reload} />}
      />
      {loading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-52 rounded-xl" />)}
        </div>
      ) : sorted.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {sorted.map((c) => (
            <Card key={c.id} className="transition-shadow hover:shadow-md">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <SchoolIcon className="size-4 text-muted-foreground" /> {c.name}
                </CardTitle>
                <CardDescription>
                  {c.total_sessions} session{c.total_sessions === 1 ? "" : "s"} · {c.cameras.length} camera{c.cameras.length === 1 ? "" : "s"}
                </CardDescription>
                <CardAction>
                  <ConfirmDialog
                    trigger={
                      <Button variant="ghost" size="icon-sm" aria-label={`Delete ${c.name}`} className="text-muted-foreground hover:text-destructive">
                        <Trash2Icon />
                      </Button>
                    }
                    title={`Delete ${c.name}?`}
                    description="Its cameras are removed. Past sessions and attendance are kept."
                    confirmLabel="Delete classroom"
                    destructive
                    onConfirm={() => remove(c)}
                  />
                </CardAction>
              </CardHeader>
              <CardContent className="flex-1">
                {c.cameras.length ? (
                  <ul className="space-y-2">{c.cameras.map((cam) => <CameraRow key={cam.id} camera={cam} />)}</ul>
                ) : (
                  <div className="flex items-center gap-3 rounded-lg border border-dashed px-3 py-4 text-sm text-muted-foreground">
                    <CctvIcon className="size-4" /> No cameras connected
                  </div>
                )}
              </CardContent>
              <CardFooter className="border-t py-3">
                <StartSessionDialog
                  defaultClassroomId={c.id}
                  trigger={
                    <Button variant="outline" size="sm" className="w-full" disabled={!c.cameras.length}>
                      <PlayIcon /> Start session here
                    </Button>
                  }
                />
              </CardFooter>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon"><SchoolIcon /></EmptyMedia>
              <EmptyTitle>No classrooms yet</EmptyTitle>
              <EmptyDescription>Add a classroom and connect a camera to start taking attendance.</EmptyDescription>
            </EmptyHeader>
            <EmptyContent><AddClassroomDialog onCreated={reload} /></EmptyContent>
          </Empty>
        </Card>
      )}
    </div>
  )
}

import { useEffect, useState, type ReactNode } from "react"
import { useNavigate } from "react-router-dom"
import { Loader2Icon, PlayIcon } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { api, notifySessionsChanged, type Overview } from "@/lib/api"

type Props = {
  trigger?: ReactNode
  defaultClassroomId?: number
}

export function StartSessionDialog({ trigger, defaultClassroomId }: Props) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [data, setData] = useState<Overview | null>(null)
  const [classroom, setClassroom] = useState<string>("")
  const [subject, setSubject] = useState<string>("none")
  const [teacher, setTeacher] = useState<string>("none")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) return
    api
      .get<Overview>("/api/overview")
      .then((d) => {
        setData(d)
        const ready = d.classrooms.filter((c) => c.cameras.some((cam) => cam.status === "active"))
        const preferred = ready.find((c) => c.id === defaultClassroomId) ?? ready[0]
        setClassroom(preferred ? String(preferred.id) : "")
      })
      .catch((e: Error) => toast.error(e.message))
  }, [open, defaultClassroomId])

  async function start() {
    setBusy(true)
    try {
      const res = await api.post<{ id: number }>("/api/sessions", {
        classroom_id: Number(classroom),
        subject_id: subject === "none" ? null : Number(subject),
        teacher_id: teacher === "none" ? null : Number(teacher),
      })
      setOpen(false)
      notifySessionsChanged()
      toast.success("Session started", { description: "Recognition is running on the classroom cameras." })
      navigate(`/live/${res.id}`)
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button>
            <PlayIcon /> Start session
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Start a class session</DialogTitle>
          <DialogDescription>
            Cameras in the classroom start recognising students right away. Attendance is saved when you end the session.
          </DialogDescription>
        </DialogHeader>
        <FieldGroup>
          <Field>
            <FieldLabel>Classroom</FieldLabel>
            <Select value={classroom} onValueChange={setClassroom} disabled={!data}>
              <SelectTrigger className="w-full [&_.select-hint]:hidden">
                <SelectValue placeholder={data ? "Choose a classroom" : "Loading…"} />
              </SelectTrigger>
              <SelectContent>
                {data?.classrooms.map((c) => {
                  const cams = c.cameras.filter((cam) => cam.status === "active").length
                  return (
                    <SelectItem key={c.id} value={String(c.id)} disabled={cams === 0}>
                      {c.name}
                      <span className="select-hint ml-auto pl-3 text-xs text-muted-foreground">
                        {cams === 0 ? "No camera" : `${cams} camera${cams > 1 ? "s" : ""}`}
                      </span>
                    </SelectItem>
                  )
                })}
              </SelectContent>
            </Select>
            <FieldDescription>Only classrooms with an active camera can run a session.</FieldDescription>
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field>
              <FieldLabel>Subject</FieldLabel>
              <Select value={subject} onValueChange={setSubject} disabled={!data}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">No subject</SelectItem>
                  {data?.subjects.map((s) => (
                    <SelectItem key={s.id} value={String(s.id)}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel>Teacher</FieldLabel>
              <Select value={teacher} onValueChange={setTeacher} disabled={!data}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">No teacher</SelectItem>
                  {data?.teachers.map((t) => (
                    <SelectItem key={t.id} value={String(t.id)}>
                      {t.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          </div>
        </FieldGroup>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={start} disabled={!classroom || busy}>
            {busy ? <Loader2Icon className="animate-spin" /> : <PlayIcon />}
            Start session
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

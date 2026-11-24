import { useMemo, useState } from "react"
import { toast } from "sonner"
import {
  GraduationCapIcon,
  Loader2Icon,
  MoreHorizontalIcon,
  PencilIcon,
  PlusIcon,
  ScanFaceIcon,
  SearchIcon,
  Trash2Icon,
} from "lucide-react"

import { ConfirmDialog } from "@/components/confirm-dialog"
import { FaceCapture } from "@/components/face-capture"
import { PageHeader } from "@/components/page-header"
import { PersonAvatar } from "@/components/person-avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useApi } from "@/hooks/use-api"
import { api, type Student, type Subject } from "@/lib/api"
import { formatRelative } from "@/lib/format"

function StudentDialog({
  open,
  onOpenChange,
  student,
  subjects,
  onSaved,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  student: Student | null
  subjects: Subject[]
  onSaved: () => void
}) {
  const editing = Boolean(student)
  const [studentId, setStudentId] = useState(student?.student_id ?? "")
  const [name, setName] = useState(student?.name ?? "")
  const [selected, setSelected] = useState<number[]>(student?.course_ids ?? [])
  const [image, setImage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canSave = studentId.trim() && name.trim() && (editing || image)

  async function save() {
    setBusy(true)
    setError(null)
    try {
      if (image) {
        await api.post("/api/students", {
          student_id: studentId.trim(),
          name: name.trim(),
          subject_ids: selected,
          image,
        })
      } else {
        await api.patch(`/api/students/${encodeURIComponent(studentId)}`, { name: name.trim(), subject_ids: selected })
      }
      toast.success(editing ? "Student updated" : "Student enrolled", {
        description: image ? `${name.trim()}'s face is ready for recognition.` : undefined,
      })
      onOpenChange(false)
      onSaved()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !busy && onOpenChange(o)}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{editing ? `Edit ${student?.name}` : "Enroll a student"}</DialogTitle>
          <DialogDescription>
            {editing
              ? "Update details or capture a new face photo to improve recognition."
              : "Capture a clear, front-facing photo. The face is converted into a recognition signature — no video is stored."}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-6 md:grid-cols-[1.1fr_1fr]">
          <FaceCapture value={image} onChange={setImage} existingPhoto={student?.photo} />
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="sid">Student ID</FieldLabel>
              <Input
                id="sid"
                value={studentId}
                onChange={(e) => setStudentId(e.target.value)}
                placeholder="e.g. 2026-CS-014"
                disabled={editing}
                autoFocus={!editing}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="sname">Full name</FieldLabel>
              <Input id="sname" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Ayesha Khan" />
            </Field>
            <Field>
              <FieldLabel>Subjects</FieldLabel>
              <div className="max-h-44 space-y-1 overflow-y-auto rounded-lg border p-1.5">
                {subjects.length ? (
                  subjects.map((s) => {
                    const checked = selected.includes(s.id)
                    return (
                      <label
                        key={s.id}
                        className="flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-1.5 text-sm hover:bg-muted"
                      >
                        <Checkbox
                          checked={checked}
                          onCheckedChange={(v) =>
                            setSelected((cur) => (v ? [...cur, s.id] : cur.filter((x) => x !== s.id)))
                          }
                        />
                        {s.name}
                      </label>
                    )
                  })
                ) : (
                  <div className="p-2 text-sm text-muted-foreground">No subjects yet — add some on the Subjects page.</div>
                )}
              </div>
              <FieldDescription>Students enrolled in a subject are marked absent if they miss its sessions.</FieldDescription>
            </Field>
            {error ? <FieldError>{error}</FieldError> : null}
          </FieldGroup>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={save} disabled={!canSave || busy}>
            {busy ? <Loader2Icon className="animate-spin" /> : <ScanFaceIcon />}
            {busy ? (image ? "Analysing face…" : "Saving…") : editing ? "Save changes" : "Enroll student"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function StudentsPage() {
  const { data, loading, reload } = useApi<Student[]>("/api/students")
  const { data: subjects } = useApi<Subject[]>("/api/subjects")
  const [query, setQuery] = useState("")
  const [dialog, setDialog] = useState<{ open: boolean; student: Student | null; key: number }>({
    open: false,
    student: null,
    key: 0,
  })

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (data ?? []).filter(
      (s) => !q || s.name.toLowerCase().includes(q) || s.student_id.toLowerCase().includes(q) || s.courses.some((c) => c.toLowerCase().includes(q))
    )
  }, [data, query])

  const openDialog = (student: Student | null) => setDialog((d) => ({ open: true, student, key: d.key + 1 }))

  async function remove(s: Student) {
    try {
      await api.del(`/api/students/${encodeURIComponent(s.student_id)}`)
      toast.success(`${s.name} removed`)
      reload()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Students"
        description="Everyone enrolled for face recognition. Students are recognised automatically in any session."
        actions={
          <Button onClick={() => openDialog(null)}>
            <PlusIcon /> Enroll student
          </Button>
        }
      />
      <div className="flex items-center justify-between gap-3">
        <div className="relative w-full sm:w-80">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by name, ID or subject…" className="pl-8" />
        </div>
        <span className="hidden text-sm text-muted-foreground sm:block">
          {data ? `${rows.length} of ${data.length} students` : ""}
        </span>
      </div>

      <Card className="py-0">
        {loading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
          </div>
        ) : rows.length ? (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="pl-4">Student</TableHead>
                <TableHead className="hidden md:table-cell">Subjects</TableHead>
                <TableHead className="text-right">Sessions</TableHead>
                <TableHead className="hidden text-right sm:table-cell">Last attended</TableHead>
                <TableHead className="w-12 pr-4" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((s) => (
                <TableRow key={s.student_id}>
                  <TableCell className="pl-4">
                    <div className="flex items-center gap-3">
                      <PersonAvatar name={s.name} src={s.photo} />
                      <div className="min-w-0">
                        <div className="font-medium">{s.name}</div>
                        <div className="font-mono text-xs text-muted-foreground">{s.student_id}</div>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    <div className="flex flex-wrap gap-1">
                      {s.courses.length ? (
                        s.courses.map((c) => (
                          <Badge key={c} variant="secondary" className="font-normal">
                            {c}
                          </Badge>
                        ))
                      ) : (
                        <span className="text-sm text-muted-foreground">—</span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-right font-medium tabular">{s.sessions_attended}</TableCell>
                  <TableCell className="hidden text-right text-muted-foreground sm:table-cell">
                    {s.last_seen ? formatRelative(s.last_seen) : "Never"}
                  </TableCell>
                  <TableCell className="pr-4 text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${s.name}`}>
                          <MoreHorizontalIcon />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-44">
                        <DropdownMenuItem onClick={() => openDialog(s)}>
                          <PencilIcon /> Edit details
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => openDialog(s)}>
                          <ScanFaceIcon /> Re-capture face
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <ConfirmDialog
                          trigger={
                            <DropdownMenuItem variant="destructive" onSelect={(e) => e.preventDefault()}>
                              <Trash2Icon /> Remove
                            </DropdownMenuItem>
                          }
                          title={`Remove ${s.name}?`}
                          description="Their face signature and subject enrolments are deleted. Past attendance records are kept."
                          confirmLabel="Remove student"
                          destructive
                          onConfirm={() => remove(s)}
                        />
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon"><GraduationCapIcon /></EmptyMedia>
              <EmptyTitle>{data?.length ? "No matching students" : "No students enrolled"}</EmptyTitle>
              <EmptyDescription>
                {data?.length ? "Try a different search." : "Enroll a student with a quick photo to start recognising them."}
              </EmptyDescription>
            </EmptyHeader>
            {!data?.length ? (
              <EmptyContent>
                <Button onClick={() => openDialog(null)}><PlusIcon /> Enroll student</Button>
              </EmptyContent>
            ) : null}
          </Empty>
        )}
      </Card>

      <StudentDialog
        key={dialog.key}
        open={dialog.open}
        onOpenChange={(open) => setDialog((d) => ({ ...d, open }))}
        student={dialog.student}
        subjects={subjects ?? []}
        onSaved={reload}
      />
    </div>
  )
}

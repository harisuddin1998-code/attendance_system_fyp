import { useState } from "react"
import { toast } from "sonner"
import { CheckCircle2Icon, CircleDashedIcon, Loader2Icon, PlusIcon, ScanFaceIcon, Trash2Icon, UsersIcon } from "lucide-react"

import { ConfirmDialog } from "@/components/confirm-dialog"
import { FaceCapture } from "@/components/face-capture"
import { PageHeader } from "@/components/page-header"
import { PersonAvatar } from "@/components/person-avatar"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { useApi } from "@/hooks/use-api"
import { api, type Teacher } from "@/lib/api"

type DialogState = { open: boolean; teacher: Teacher | null; key: number }

function TeacherDialog({
  state,
  onOpenChange,
  onSaved,
}: {
  state: DialogState
  onOpenChange: (o: boolean) => void
  onSaved: () => void
}) {
  const teacher = state.teacher
  const [name, setName] = useState("")
  const [image, setImage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function save() {
    setBusy(true)
    setError(null)
    try {
      if (teacher) {
        await api.post(`/api/teachers/${teacher.id}/face`, { image })
        toast.success(`Face enrolled for ${teacher.name}`)
      } else {
        await api.post("/api/teachers", { name: name.trim(), image })
        toast.success(`${name.trim()} added`)
      }
      onOpenChange(false)
      onSaved()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const canSave = teacher ? Boolean(image) : Boolean(name.trim())

  return (
    <Dialog open={state.open} onOpenChange={(o) => !busy && onOpenChange(o)}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{teacher ? `Enroll ${teacher.name}'s face` : "Add a teacher"}</DialogTitle>
          <DialogDescription>
            {teacher
              ? "Once enrolled, the teacher's presence is logged automatically in their sessions."
              : "A face photo is optional now — you can enroll it later."}
          </DialogDescription>
        </DialogHeader>
        <FieldGroup>
          {!teacher ? (
            <Field>
              <FieldLabel htmlFor="tname">Full name</FieldLabel>
              <Input id="tname" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Dr. Sara Malik" autoFocus />
            </Field>
          ) : null}
          <Field>
            {!teacher ? <FieldLabel>Face photo</FieldLabel> : null}
            <FaceCapture value={image} onChange={setImage} existingPhoto={teacher?.photo} />
            {!teacher ? <FieldDescription>Optional</FieldDescription> : null}
          </Field>
          {error ? <FieldError>{error}</FieldError> : null}
        </FieldGroup>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>Cancel</Button>
          <Button onClick={save} disabled={!canSave || busy}>
            {busy ? <Loader2Icon className="animate-spin" /> : teacher ? <ScanFaceIcon /> : <PlusIcon />}
            {busy ? (image ? "Analysing face…" : "Saving…") : teacher ? "Enroll face" : "Add teacher"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function TeachersPage() {
  const { data, loading, reload } = useApi<Teacher[]>("/api/teachers")
  const [dialog, setDialog] = useState<DialogState>({ open: false, teacher: null, key: 0 })
  const open = (teacher: Teacher | null) => setDialog((d) => ({ open: true, teacher, key: d.key + 1 }))

  async function remove(t: Teacher) {
    try {
      await api.del(`/api/teachers/${t.id}`)
      toast.success(`${t.name} removed`)
      reload()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Teachers"
        description="Teachers with an enrolled face are logged automatically when they appear in their sessions."
        actions={<Button onClick={() => open(null)}><PlusIcon /> Add teacher</Button>}
      />
      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-40 rounded-xl" />)}
        </div>
      ) : data?.length ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {data.map((t) => (
            <Card key={t.id} className="transition-shadow hover:shadow-md">
              <CardContent className="flex items-center gap-4">
                <PersonAvatar name={t.name} src={t.photo} size="xl" />
                <div className="min-w-0 flex-1 space-y-1.5">
                  <div className="truncate font-semibold">{t.name}</div>
                  {t.has_face ? (
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                      <CheckCircle2Icon className="size-3.5" /> Face enrolled
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground">
                      <CircleDashedIcon className="size-3.5" /> No face enrolled
                    </span>
                  )}
                  <div className="text-xs text-muted-foreground">{t.sessions ?? 0} session{t.sessions === 1 ? "" : "s"} taught</div>
                </div>
              </CardContent>
              <CardFooter className="justify-between gap-2 border-t py-3">
                <Button variant={t.has_face ? "outline" : "default"} size="sm" onClick={() => open(t)}>
                  <ScanFaceIcon /> {t.has_face ? "Update face" : "Enroll face"}
                </Button>
                <ConfirmDialog
                  trigger={
                    <Button variant="ghost" size="icon-sm" aria-label={`Remove ${t.name}`} className="text-muted-foreground hover:text-destructive">
                      <Trash2Icon />
                    </Button>
                  }
                  title={`Remove ${t.name}?`}
                  description="They'll be unassigned from past sessions. Attendance history is kept."
                  confirmLabel="Remove teacher"
                  destructive
                  onConfirm={() => remove(t)}
                />
              </CardFooter>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon"><UsersIcon /></EmptyMedia>
              <EmptyTitle>No teachers yet</EmptyTitle>
              <EmptyDescription>Add teachers to assign them to sessions.</EmptyDescription>
            </EmptyHeader>
            <EmptyContent><Button onClick={() => open(null)}><PlusIcon /> Add teacher</Button></EmptyContent>
          </Empty>
        </Card>
      )}
      <TeacherDialog key={dialog.key} state={dialog} onOpenChange={(o) => setDialog((d) => ({ ...d, open: o }))} onSaved={reload} />
    </div>
  )
}

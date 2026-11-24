import { useState, type FormEvent } from "react"
import { toast } from "sonner"
import { BookOpenIcon, Loader2Icon, PlusIcon, Trash2Icon } from "lucide-react"

import { ConfirmDialog } from "@/components/confirm-dialog"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useApi } from "@/hooks/use-api"
import { api, type Subject } from "@/lib/api"

export default function SubjectsPage() {
  const { data, loading, reload } = useApi<Subject[]>("/api/subjects")
  const [name, setName] = useState("")
  const [busy, setBusy] = useState(false)

  async function add(e: FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    setBusy(true)
    try {
      await api.post("/api/subjects", { name: name.trim() })
      toast.success(`${name.trim()} added`)
      setName("")
      reload()
    } catch (err) {
      toast.error((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function remove(s: Subject) {
    try {
      await api.del(`/api/subjects/${s.id}`)
      toast.success(`${s.name} deleted`)
      reload()
    } catch (err) {
      toast.error((err as Error).message)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Subjects" description="Courses that sessions are run for and students enrol in." />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <Card className="order-2 py-0 lg:order-1">
          {loading ? (
            <div className="space-y-2 p-4">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-11 w-full" />)}</div>
          ) : data?.length ? (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="pl-4">Subject</TableHead>
                  <TableHead className="text-right">Students</TableHead>
                  <TableHead className="text-right">Sessions</TableHead>
                  <TableHead className="w-12 pr-4" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell className="pl-4">
                      <div className="flex items-center gap-3">
                        <span className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                          <BookOpenIcon className="size-4" />
                        </span>
                        <span className="font-medium">{s.name}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-right tabular">{s.students ?? 0}</TableCell>
                    <TableCell className="text-right tabular">{s.sessions ?? 0}</TableCell>
                    <TableCell className="pr-4 text-right">
                      <ConfirmDialog
                        trigger={
                          <Button variant="ghost" size="icon-sm" aria-label={`Delete ${s.name}`} className="text-muted-foreground hover:text-destructive">
                            <Trash2Icon />
                          </Button>
                        }
                        title={`Delete ${s.name}?`}
                        description="Students are un-enrolled from it. Past sessions and their attendance are kept, without a subject."
                        confirmLabel="Delete subject"
                        destructive
                        onConfirm={() => remove(s)}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon"><BookOpenIcon /></EmptyMedia>
                <EmptyTitle>No subjects yet</EmptyTitle>
                <EmptyDescription>Add your first subject using the form.</EmptyDescription>
              </EmptyHeader>
            </Empty>
          )}
        </Card>
        <Card className="order-1 h-fit lg:order-2">
          <CardHeader>
            <CardTitle>New subject</CardTitle>
            <CardDescription>Appears when starting a session and enrolling students.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={add} className="flex flex-col gap-3">
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Data Structures" aria-label="Subject name" />
              <Button type="submit" disabled={!name.trim() || busy}>
                {busy ? <Loader2Icon className="animate-spin" /> : <PlusIcon />} Add subject
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

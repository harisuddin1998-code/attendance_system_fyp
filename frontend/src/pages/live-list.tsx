import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { ArrowRightIcon, BookOpenIcon, RadioIcon, SchoolIcon, UserIcon } from "lucide-react"

import { PageHeader } from "@/components/page-header"
import { StartSessionDialog } from "@/components/start-session-dialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { useApi } from "@/hooks/use-api"
import type { SessionRow } from "@/lib/api"
import { formatClock, formatTime, sessionSeconds, sessionTitle } from "@/lib/format"

function useNow(ms = 1000) {
  const [, setTick] = useState(0)
  useEffect(() => {
    const id = window.setInterval(() => setTick((t) => t + 1), ms)
    return () => window.clearInterval(id)
  }, [ms])
}

export default function LiveListPage() {
  const { data, loading } = useApi<SessionRow[]>("/api/sessions?status=Ongoing", { interval: 5000 })
  useNow()

  return (
    <div className="space-y-8">
      <PageHeader
        title="Live sessions"
        description="Sessions that are recording attendance right now. Open one to watch the cameras and see who's in the room."
      />
      {loading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-48 rounded-xl" />
          ))}
        </div>
      ) : data && data.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data.map((s) => (
            <Card key={s.id} className="transition-shadow hover:shadow-md">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
                    <span className="size-1.5 animate-pulse rounded-full bg-primary" /> Live
                  </span>
                  <span className="font-mono text-sm text-muted-foreground tabular">
                    {formatClock(sessionSeconds(s.start_time, null))}
                  </span>
                </div>
                <CardTitle className="pt-2 text-base">{sessionTitle(s)}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-muted-foreground">
                <div className="flex items-center gap-2">
                  <SchoolIcon className="size-4" /> {s.classroom_name ?? "Classroom"}
                </div>
                <div className="flex items-center gap-2">
                  <UserIcon className="size-4" /> {s.teacher_name ?? "No teacher assigned"}
                </div>
                <div className="flex items-center gap-2">
                  <BookOpenIcon className="size-4" /> Started at {formatTime(s.start_time)}
                </div>
              </CardContent>
              <CardFooter className="border-t py-3">
                <Button asChild className="w-full">
                  <Link to={`/live/${s.id}`}>
                    Open live view <ArrowRightIcon />
                  </Link>
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <RadioIcon />
              </EmptyMedia>
              <EmptyTitle>Nothing is live</EmptyTitle>
              <EmptyDescription>Start a session to begin taking attendance with the classroom cameras.</EmptyDescription>
            </EmptyHeader>
            <EmptyContent>
              <StartSessionDialog />
            </EmptyContent>
          </Empty>
        </Card>
      )}
    </div>
  )
}

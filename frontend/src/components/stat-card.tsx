import type { LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

import { Card } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

type Props = {
  label: string
  value: ReactNode
  hint?: ReactNode
  icon: LucideIcon
  loading?: boolean
  accent?: string
}

export function StatCard({ label, value, hint, icon: Icon, loading, accent }: Props) {
  return (
    <Card className="gap-0 p-4 sm:p-5">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground sm:text-sm">{label}</span>
        <span className={cn("flex size-8 items-center justify-center rounded-lg bg-muted text-muted-foreground", accent)}>
          <Icon className="size-4" />
        </span>
      </div>
      {loading ? (
        <Skeleton className="mt-3 h-8 w-20" />
      ) : (
        <div className="mt-2 text-2xl font-semibold tracking-tight tabular sm:text-3xl">{value}</div>
      )}
      {hint ? <div className="mt-1 text-xs text-muted-foreground">{hint}</div> : null}
    </Card>
  )
}

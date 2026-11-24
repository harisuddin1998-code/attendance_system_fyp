import { cn } from "@/lib/utils"

const STYLES: Record<string, { dot: string; badge: string; label?: string }> = {
  Present: {
    dot: "bg-emerald-500",
    badge: "bg-emerald-500/10 text-emerald-700 ring-emerald-600/15 dark:text-emerald-300 dark:ring-emerald-400/20",
  },
  Late: {
    dot: "bg-amber-500",
    badge: "bg-amber-500/10 text-amber-700 ring-amber-600/20 dark:text-amber-300 dark:ring-amber-400/20",
  },
  "Early Leave": {
    dot: "bg-orange-500",
    badge: "bg-orange-500/10 text-orange-700 ring-orange-600/20 dark:text-orange-300 dark:ring-orange-400/20",
  },
  Absent: {
    dot: "bg-rose-500",
    badge: "bg-rose-500/10 text-rose-700 ring-rose-600/15 dark:text-rose-300 dark:ring-rose-400/20",
  },
  Ongoing: {
    dot: "bg-primary animate-pulse",
    badge: "bg-primary/10 text-primary ring-primary/20",
    label: "Live",
  },
  Ended: {
    dot: "bg-muted-foreground/60",
    badge: "bg-muted text-muted-foreground ring-border",
    label: "Completed",
  },
}

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const style = STYLES[status] ?? STYLES.Ended
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-full px-2.5 text-xs font-medium whitespace-nowrap ring-1 ring-inset",
        style.badge,
        className
      )}
    >
      <span className={cn("size-1.5 rounded-full", style.dot)} />
      {style.label ?? status}
    </span>
  )
}

export const STATUS_COLORS: Record<string, string> = {
  Present: "bg-emerald-500",
  Late: "bg-amber-500",
  "Early Leave": "bg-orange-500",
  Absent: "bg-rose-500",
}

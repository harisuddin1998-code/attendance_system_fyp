import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { initials } from "@/lib/format"
import { cn } from "@/lib/utils"

const TINTS = [
  "bg-indigo-500/12 text-indigo-700 dark:text-indigo-300",
  "bg-sky-500/12 text-sky-700 dark:text-sky-300",
  "bg-teal-500/12 text-teal-700 dark:text-teal-300",
  "bg-violet-500/12 text-violet-700 dark:text-violet-300",
  "bg-slate-500/12 text-slate-700 dark:text-slate-300",
  "bg-cyan-500/12 text-cyan-700 dark:text-cyan-300",
]

function tint(name: string) {
  let h = 0
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0
  return TINTS[h % TINTS.length]
}

type Props = {
  name: string
  src?: string | null
  size?: "sm" | "md" | "lg" | "xl"
  className?: string
}

const SIZES = {
  sm: "size-7 text-[10px]",
  md: "size-9 text-xs",
  lg: "size-11 text-sm",
  xl: "size-16 text-base",
}

export function PersonAvatar({ name, src, size = "md", className }: Props) {
  return (
    <Avatar className={cn(SIZES[size], "ring-1 ring-foreground/5", className)}>
      {src ? <AvatarImage src={src} alt={name} className="object-cover" /> : null}
      <AvatarFallback className={cn("font-semibold", tint(name))}>{initials(name) || "?"}</AvatarFallback>
    </Avatar>
  )
}

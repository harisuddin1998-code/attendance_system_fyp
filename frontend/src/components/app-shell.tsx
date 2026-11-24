import { useEffect } from "react"
import { Link, Outlet, useLocation } from "react-router-dom"
import {
  BookOpenIcon,
  GraduationCapIcon,
  HistoryIcon,
  LayoutDashboardIcon,
  MonitorIcon,
  MoonIcon,
  RadioIcon,
  ScanFaceIcon,
  SchoolIcon,
  SunIcon,
  UsersIcon,
  type LucideIcon,
} from "lucide-react"

import { StartSessionDialog } from "@/components/start-session-dialog"
import { useTheme } from "@/components/theme-provider"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Separator } from "@/components/ui/separator"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar"
import { useApi } from "@/hooks/use-api"
import { SESSIONS_CHANGED, type SessionRow } from "@/lib/api"

type NavItem = { title: string; to: string; icon: LucideIcon; match?: (path: string) => boolean }

const NAV: { label: string; items: NavItem[] }[] = [
  {
    label: "Overview",
    items: [
      { title: "Dashboard", to: "/", icon: LayoutDashboardIcon, match: (p) => p === "/" },
      { title: "Live sessions", to: "/live", icon: RadioIcon },
      { title: "Session history", to: "/sessions", icon: HistoryIcon },
    ],
  },
  {
    label: "Directory",
    items: [
      { title: "Students", to: "/students", icon: GraduationCapIcon },
      { title: "Teachers", to: "/teachers", icon: UsersIcon },
      { title: "Subjects", to: "/subjects", icon: BookOpenIcon },
      { title: "Classrooms", to: "/classrooms", icon: SchoolIcon },
    ],
  },
]

const TITLES: [RegExp, string][] = [
  [/^\/$/, "Dashboard"],
  [/^\/live\/\d+/, "Live session"],
  [/^\/live/, "Live sessions"],
  [/^\/sessions\/\d+/, "Attendance report"],
  [/^\/sessions/, "Session history"],
  [/^\/students/, "Students"],
  [/^\/teachers/, "Teachers"],
  [/^\/subjects/, "Subjects"],
  [/^\/classrooms/, "Classrooms"],
]

function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const Icon = theme === "dark" ? MoonIcon : theme === "light" ? SunIcon : MonitorIcon
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <SidebarMenuButton tooltip="Appearance">
          <Icon />
          <span>Appearance</span>
          <span className="ml-auto text-xs text-muted-foreground capitalize">{theme}</span>
        </SidebarMenuButton>
      </DropdownMenuTrigger>
      <DropdownMenuContent side="top" align="start" className="w-44">
        <DropdownMenuItem onClick={() => setTheme("light")}>
          <SunIcon /> Light
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTheme("dark")}>
          <MoonIcon /> Dark
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTheme("system")}>
          <MonitorIcon /> System
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function AppSidebar() {
  const { pathname } = useLocation()
  const { setOpenMobile } = useSidebar()
  const { data: live, reload } = useApi<SessionRow[]>("/api/sessions?status=Ongoing", { interval: 10000 })
  const liveCount = live?.length ?? 0

  useEffect(() => {
    const onChange = () => void reload()
    window.addEventListener(SESSIONS_CHANGED, onChange)
    return () => window.removeEventListener(SESSIONS_CHANGED, onChange)
  }, [reload])

  return (
    <Sidebar variant="inset" collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link to="/" onClick={() => setOpenMobile(false)}>
                <span className="flex aspect-square size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
                  <ScanFaceIcon className="size-4.5" />
                </span>
                <span className="grid flex-1 text-left leading-tight">
                  <span className="truncate font-semibold tracking-tight">Vision Sentinal</span>
                  <span className="truncate text-xs text-muted-foreground">Face recognition</span>
                </span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        {NAV.map((group) => (
          <SidebarGroup key={group.label}>
            <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {group.items.map((item) => {
                  const active = item.match ? item.match(pathname) : pathname.startsWith(item.to)
                  return (
                    <SidebarMenuItem key={item.to}>
                      <SidebarMenuButton asChild isActive={active} tooltip={item.title}>
                        <Link to={item.to} onClick={() => setOpenMobile(false)}>
                          <item.icon />
                          <span>{item.title}</span>
                        </Link>
                      </SidebarMenuButton>
                      {item.to === "/live" && liveCount > 0 ? (
                        <SidebarMenuBadge className="gap-1.5 text-primary">
                          <span className="size-1.5 animate-pulse rounded-full bg-primary" />
                          {liveCount}
                        </SidebarMenuBadge>
                      ) : null}
                    </SidebarMenuItem>
                  )
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <ThemeToggle />
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}

export function AppShell() {
  const { pathname } = useLocation()
  const title = TITLES.find(([re]) => re.test(pathname))?.[1] ?? "Vision Sentinal"

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset className="min-w-0">
        <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-2 rounded-t-xl border-b bg-background/80 px-4 backdrop-blur-md">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-1 data-[orientation=vertical]:h-4" />
          <span className="truncate text-sm font-medium">{title}</span>
          <div className="ml-auto">
            <StartSessionDialog
              trigger={
                <Button size="sm">
                  <RadioIcon /> <span className="hidden sm:inline">Start session</span>
                </Button>
              }
            />
          </div>
        </header>
        <div key={pathname} className="page-enter mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}

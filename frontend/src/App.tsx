import { BrowserRouter, Link, Route, Routes } from "react-router-dom"

import { AppShell } from "@/components/app-shell"
import { Button } from "@/components/ui/button"
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import ClassroomsPage from "@/pages/classrooms"
import DashboardPage from "@/pages/dashboard"
import LiveListPage from "@/pages/live-list"
import LiveSessionPage from "@/pages/live-session"
import ReportPage from "@/pages/report"
import SessionsPage from "@/pages/sessions"
import StudentsPage from "@/pages/students"
import SubjectsPage from "@/pages/subjects"
import TeachersPage from "@/pages/teachers"

function NotFound() {
  return (
    <Empty>
      <EmptyHeader>
        <EmptyTitle>Page not found</EmptyTitle>
        <EmptyDescription>The page you're looking for doesn't exist.</EmptyDescription>
      </EmptyHeader>
      <Button asChild variant="outline">
        <Link to="/">Go to dashboard</Link>
      </Button>
    </Empty>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="live" element={<LiveListPage />} />
          <Route path="live/:id" element={<LiveSessionPage />} />
          <Route path="sessions" element={<SessionsPage />} />
          <Route path="sessions/:id" element={<ReportPage />} />
          <Route path="students" element={<StudentsPage />} />
          <Route path="teachers" element={<TeachersPage />} />
          <Route path="subjects" element={<SubjectsPage />} />
          <Route path="classrooms" element={<ClassroomsPage />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

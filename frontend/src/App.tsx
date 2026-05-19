import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useAuthStore } from "@/stores/auth";
import AppLayout from "@/layouts/AppLayout";
import LoginPage from "@/pages/auth/LoginPage";
import MicrosoftCallbackPage from "@/pages/auth/MicrosoftCallbackPage";
import DashboardPage from "@/pages/dashboard/DashboardPage";
import GoalsPage from "@/pages/goals/GoalsPage";
import TeamPage from "@/pages/team/TeamPage";
import CheckinsPage from "@/pages/team/CheckinsPage";
import AnalyticsPage from "@/pages/analytics/AnalyticsPage";
import CyclesPage from "@/pages/admin/CyclesPage";
import EscalationsPage from "@/pages/admin/EscalationsPage";
import NotificationsPage from "@/pages/admin/NotificationsPage";
import ReportsPage from "@/pages/admin/ReportsPage";
import AuditPage from "@/pages/admin/AuditPage";
import type { UserRole } from "@/types/api";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

/* ── Guard Components ────────────────────────────────────────────────── */
function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.token);
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function RequireRole({
  roles,
  children,
}: {
  roles: UserRole[];
  children: React.ReactNode;
}) {
  const user = useAuthStore((s) => s.user);
  if (!user || !roles.includes(user.role))
    return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/auth/callback" element={<MicrosoftCallbackPage />} />

          {/* Authenticated */}
          <Route
            element={
              <RequireAuth>
                <AppLayout />
              </RequireAuth>
            }
          >
            {/* Dashboard — all roles */}
            <Route path="/" element={<DashboardPage />} />

            {/* Employee */}
            <Route
              path="/goals"
              element={
                <RequireRole roles={["EMPLOYEE"]}>
                  <GoalsPage />
                </RequireRole>
              }
            />

            {/* Manager */}
            <Route
              path="/team"
              element={
                <RequireRole roles={["MANAGER", "ADMIN"]}>
                  <TeamPage />
                </RequireRole>
              }
            />
            <Route
              path="/team/checkins"
              element={
                <RequireRole roles={["MANAGER", "ADMIN"]}>
                  <CheckinsPage />
                </RequireRole>
              }
            />

            {/* Analytics — Manager + Admin */}
            <Route
              path="/analytics"
              element={
                <RequireRole roles={["MANAGER", "ADMIN"]}>
                  <AnalyticsPage />
                </RequireRole>
              }
            />

            {/* Admin */}
            <Route
              path="/admin/cycles"
              element={
                <RequireRole roles={["ADMIN"]}>
                  <CyclesPage />
                </RequireRole>
              }
            />
            <Route
              path="/admin/escalations"
              element={
                <RequireRole roles={["ADMIN"]}>
                  <EscalationsPage />
                </RequireRole>
              }
            />
            <Route
              path="/admin/notifications"
              element={
                <RequireRole roles={["ADMIN"]}>
                  <NotificationsPage />
                </RequireRole>
              }
            />
            <Route
              path="/admin/reports"
              element={
                <RequireRole roles={["ADMIN"]}>
                  <ReportsPage />
                </RequireRole>
              }
            />
            <Route
              path="/admin/audit"
              element={
                <RequireRole roles={["ADMIN"]}>
                  <AuditPage />
                </RequireRole>
              }
            />
          </Route>

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

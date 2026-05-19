import { NavLink, Outlet, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  Atom,
  BarChart3,
  Bell,
  ClipboardCheck,
  FileText,
  LayoutDashboard,
  ScrollText,
  LogOut,
  Settings,
  Target,
  Users,
} from "lucide-react";
import { authApi } from "@/api/endpoints";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth";
import type { UserRole } from "@/types/api";

interface NavItem {
  to: string;
  label: string;
  icon: React.ElementType;
  roles: UserRole[];
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, roles: ["EMPLOYEE", "MANAGER", "ADMIN"] },
  { to: "/goals", label: "My Goals", icon: Target, roles: ["EMPLOYEE"] },
  { to: "/team", label: "Goal Review", icon: Users, roles: ["MANAGER", "ADMIN"] },
  { to: "/team/checkins", label: "Check-ins", icon: ClipboardCheck, roles: ["MANAGER", "ADMIN"] },
  { to: "/analytics", label: "Analytics", icon: BarChart3, roles: ["MANAGER", "ADMIN"] },
  { to: "/admin/cycles", label: "Cycles", icon: Settings, roles: ["ADMIN"] },
  { to: "/admin/escalations", label: "Escalations", icon: AlertTriangle, roles: ["ADMIN"] },
  { to: "/admin/notifications", label: "Notifications", icon: Bell, roles: ["ADMIN"] },
  { to: "/admin/reports", label: "Reports", icon: FileText, roles: ["ADMIN"] },
  { to: "/admin/audit", label: "Audit", icon: ScrollText, roles: ["ADMIN"] },
];

const PAGE_LABELS: Record<string, string> = {
  "/": "Dashboard",
  "/goals": "Goal Sheet",
  "/team": "Goal Review",
  "/team/checkins": "Quarterly Check-ins",
  "/analytics": "Analytics",
  "/admin/cycles": "Cycle Setup",
  "/admin/escalations": "Escalations",
  "/admin/notifications": "Notifications",
  "/admin/reports": "Reports",
  "/admin/audit": "Audit Trail",
};

export default function AppLayout() {
  const { user, logout } = useAuthStore();
  const location = useLocation();

  if (!user) return null;

  const visibleItems = NAV_ITEMS.filter((item) => item.roles.includes(user.role));
  const initials = user.name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch {
      // Local logout still clears the session if the backend token is already gone.
    }
    logout();
  };

  return (
    <div className="min-h-screen lg:flex">
      <aside className="hidden w-72 shrink-0 flex-col border-r border-white/10 bg-[var(--sidebar-bg)] text-[var(--sidebar-fg)] lg:flex">
        <div className="border-b border-white/10 px-5 py-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--sidebar-active)] text-[var(--primary)]">
              <Atom className="h-5 w-5" />
            </div>
            <div>
              <p className="text-base font-semibold text-white">AtomQuest</p>
              <p className="text-xs text-[var(--sidebar-fg)]">Goal operations portal</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-4">
          {visibleItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-[var(--sidebar-active)] text-[var(--sidebar-bg)]"
                    : "hover:bg-[var(--sidebar-hover)] hover:text-white",
                )
              }
            >
              <item.icon className="h-4 w-4 shrink-0" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-white/10 p-4">
          <div className="mb-3 flex items-center gap-3 rounded-lg bg-white/5 p-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-white text-xs font-semibold text-[var(--sidebar-bg)]">
              {initials}
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-white">{user.name}</p>
              <p className="truncate text-xs">
                {user.role}
                {user.department ? ` / ${user.department}` : ""}
              </p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors hover:bg-[var(--sidebar-hover)] hover:text-white"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      </aside>

      <div className="flex min-h-screen min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 border-b border-[var(--border)] bg-white/85 backdrop-blur-xl">
          <div className="flex min-h-16 items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
            <div className="min-w-0">
              <p className="page-kicker">AtomQuest / {PAGE_LABELS[location.pathname] ?? "Workspace"}</p>
              <h1 className="truncate text-lg font-semibold text-[var(--foreground)]">
                {PAGE_LABELS[location.pathname] ?? "Workspace"}
              </h1>
            </div>
          </div>

          <nav className="flex gap-1 overflow-x-auto border-t border-[var(--border)] px-3 py-2 lg:hidden">
            {visibleItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  cn(
                    "flex h-9 shrink-0 items-center gap-2 rounded-md px-3 text-xs font-medium",
                    isActive
                      ? "bg-[var(--primary)] text-white"
                      : "bg-white text-[var(--muted-foreground)]",
                  )
                }
              >
                <item.icon className="h-3.5 w-3.5" />
                {item.label}
              </NavLink>
            ))}
          </nav>
        </header>

        <main className="flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
              className="mx-auto max-w-7xl"
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}

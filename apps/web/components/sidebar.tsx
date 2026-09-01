"use client";

import {
  BarChart3,
  Camera,
  ClipboardList,
  FileText,
  GitBranch,
  Landmark,
  LayoutDashboard,
  ListChecks,
  LogOut,
  type LucideIcon,
  MessageCirclePlus,
  Radar,
  Settings,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  Upload,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const GROUPS: NavGroup[] = [
  {
    label: "Overview",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/trends", label: "Trends", icon: TrendingUp },
      { href: "/snapshots", label: "Snapshots", icon: Camera },
    ],
  },
  {
    label: "Risk Register",
    items: [
      { href: "/risk-intake", label: "Report a Risk", icon: MessageCirclePlus },
      { href: "/risks", label: "Risk Register", icon: ClipboardList },
      { href: "/controls", label: "Controls", icon: ShieldCheck },
      { href: "/actions", label: "Actions", icon: ListChecks },
      { href: "/governance", label: "Governance", icon: Landmark },
    ],
  },
  {
    label: "Quantitative Analysis",
    items: [
      { href: "/simulations", label: "Simulations", icon: BarChart3 },
      { href: "/scenarios", label: "Scenarios", icon: GitBranch },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { href: "/ai", label: "AI Insights", icon: Sparkles },
      { href: "/emerging-risks", label: "Emerging Risks", icon: Radar },
    ],
  },
  {
    label: "Reporting & Data",
    items: [
      { href: "/reports", label: "Reports", icon: FileText },
      { href: "/imports", label: "Import Wizard", icon: Upload },
    ],
  },
];

const ADMIN_GROUP: NavGroup = {
  label: "Administration",
  items: [
    { href: "/admin/scoring-config", label: "Scoring Config", icon: Settings },
    { href: "/admin/appetite", label: "Risk Appetite", icon: Target },
  ],
};

function initialsFor(name: string): string {
  return (
    name
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0])
      .join("")
      .toUpperCase() || "?"
  );
}

export function Sidebar({
  mobileOpen,
  onCloseMobile,
}: {
  mobileOpen: boolean;
  onCloseMobile: () => void;
}) {
  const { session, logout } = useAuth();
  const pathname = usePathname();

  if (!session) return null;

  const groups = session.roles.includes("administrator") ? [...GROUPS, ADMIN_GROUP] : GROUPS;

  return (
    <>
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-slate-900/30 lg:hidden"
          onClick={onCloseMobile}
          aria-hidden="true"
        />
      )}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex h-screen w-64 shrink-0 flex-col border-r border-surface-border bg-white transition-transform duration-200 ease-in-out",
          "lg:static lg:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center justify-between gap-2 border-b border-surface-border px-5 py-5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent text-sm font-bold text-white">
              R
            </div>
            <span className="text-sm font-semibold leading-tight text-slate-900">
              Risk Intelligence
              <br />
              Platform
            </span>
          </div>
          <button
            onClick={onCloseMobile}
            className="rounded-md p-1 text-slate-400 hover:bg-surface-muted lg:hidden"
            aria-label="Close navigation"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-5">
          {groups.map((group) => (
            <div key={group.label}>
              <p className="px-2.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                {group.label}
              </p>
              <div className="mt-1.5 space-y-0.5">
                {group.items.map((item) => {
                  const active = pathname?.startsWith(item.href) ?? false;
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={onCloseMobile}
                      className={cn(
                        "flex items-center gap-2.5 rounded-md border-l-2 px-2.5 py-2 text-sm font-medium transition-colors",
                        active
                          ? "border-accent bg-accent-soft text-accent"
                          : "border-transparent text-slate-600 hover:bg-surface-muted hover:text-slate-900",
                      )}
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      <span className="truncate">{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-surface-border p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-200 text-xs font-semibold text-slate-700">
              {initialsFor(session.display_name)}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-slate-900">{session.display_name}</p>
              <p className="truncate text-xs capitalize text-slate-500">{session.roles.join(", ")}</p>
            </div>
            <button
              onClick={logout}
              title="Sign out"
              className="shrink-0 rounded-md p-1.5 text-slate-400 hover:bg-surface-muted hover:text-slate-700"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}

"use client";

import { Menu } from "lucide-react";
import { ReactNode, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { Sidebar } from "@/components/sidebar";

export function AppShell({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  if (!session) {
    return <main className="min-h-screen">{children}</main>;
  }

  return (
    <div className="flex min-h-screen bg-surface-muted">
      <Sidebar mobileOpen={mobileNavOpen} onCloseMobile={() => setMobileNavOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center border-b border-surface-border bg-white px-4 py-3 lg:hidden">
          <button
            onClick={() => setMobileNavOpen(true)}
            className="rounded-md p-1.5 text-slate-500 hover:bg-surface-muted"
            aria-label="Open navigation"
          >
            <Menu className="h-5 w-5" />
          </button>
          <span className="ml-3 text-sm font-semibold text-slate-900">Risk Intelligence Platform</span>
        </header>
        <main className="flex-1 overflow-x-hidden px-6 py-8 lg:px-10">
          <div className="mx-auto max-w-7xl">{children}</div>
        </main>
      </div>
    </div>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/risks", label: "Risk Register" },
  { href: "/imports", label: "Import Wizard" },
];

export function Nav() {
  const { session, logout } = useAuth();
  const pathname = usePathname();

  return (
    <nav className="border-b border-surface-border bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <div className="flex items-center gap-6">
          <span className="font-semibold text-slate-900">Risk Intelligence Platform</span>
          {session &&
            LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "text-sm text-slate-600 hover:text-slate-900",
                  pathname?.startsWith(link.href) && "font-medium text-slate-900",
                )}
              >
                {link.label}
              </Link>
            ))}
        </div>
        {session && (
          <div className="flex items-center gap-3 text-sm text-slate-600">
            <span>
              {session.display_name} · {session.roles.join(", ")}
            </span>
            <button onClick={logout} className="text-slate-500 hover:text-slate-900">
              Sign out
            </button>
          </div>
        )}
      </div>
    </nav>
  );
}

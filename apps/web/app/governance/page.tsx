"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { RequireAuth } from "@/components/require-auth";
import { KpiTile } from "@/components/ui/kpi-tile";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { apiFetch } from "@/lib/api";
import type { GovernanceHealth } from "@/lib/types";

const APPETITE_LABELS: Record<string, string> = {
  within_appetite: "Within appetite",
  approaching_tolerance: "Approaching tolerance",
  outside_appetite: "Outside appetite",
  material_breach: "Material breach",
  not_configured: "Not configured",
};

function GovernanceHealthView() {
  const [data, setData] = useState<GovernanceHealth | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<GovernanceHealth>("/api/v1/dashboard/governance")
      .then(setData)
      .catch((err) => setError(String(err)));
  }, []);

  if (error) return <p className="text-sm text-severity-extreme">{error}</p>;
  if (!data) return <p className="text-sm text-slate-500">Loading…</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">Governance Health</h1>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <KpiTile label="Weak controls" value={data.weak_controls_count} tone="extreme" />
        <KpiTile label="Overdue actions" value={data.overdue_actions_count} tone="high" />
        <KpiTile label="Overdue reviews" value={data.overdue_reviews_count} tone="moderate" />
      </div>

      <div className="rounded-lg border border-surface-border bg-white p-4 shadow-card">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">Risk Appetite Status</h2>
        <div className="flex flex-wrap gap-4 text-sm">
          {Object.entries(APPETITE_LABELS).map(([key, label]) => (
            <div key={key} className="flex items-center gap-2">
              <span className="text-slate-500">{label}:</span>
              <span className="font-medium text-slate-900">{data.appetite_status_counts[key] ?? 0}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-lg border border-surface-border bg-white p-4 shadow-card">
          <h2 className="mb-3 text-sm font-semibold text-slate-900">Weak Controls</h2>
          <ul className="space-y-2 text-sm">
            {data.weak_controls.map((c) => (
              <li key={c.id} className="flex items-center justify-between border-b border-surface-border pb-2 last:border-0">
                <Link href={`/controls/${c.id}`} className="hover:underline">
                  {c.name}
                </Link>
                <span className="text-severity-extreme">{c.operating_effectiveness ?? c.design_effectiveness}/5</span>
              </li>
            ))}
            {data.weak_controls.length === 0 && <li className="text-slate-500">No weak controls.</li>}
          </ul>
        </div>

        <div className="rounded-lg border border-surface-border bg-white p-4 shadow-card">
          <h2 className="mb-3 text-sm font-semibold text-slate-900">Overdue Actions</h2>
          <ul className="space-y-2 text-sm">
            {data.overdue_actions.map((a) => (
              <li key={a.id} className="flex items-center justify-between border-b border-surface-border pb-2 last:border-0">
                <span>{a.title}</span>
                <span className="text-slate-500">{a.due_date}</span>
              </li>
            ))}
            {data.overdue_actions.length === 0 && <li className="text-slate-500">No overdue actions.</li>}
          </ul>
        </div>
      </div>

      <div className="rounded-lg border border-surface-border bg-white p-4 shadow-card">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">Risks Outside Appetite</h2>
        <table className="w-full text-sm">
          <thead className="border-b border-surface-border text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="py-2">Risk</th>
              <th className="py-2">Band</th>
              <th className="py-2">Appetite status</th>
            </tr>
          </thead>
          <tbody>
            {data.breach_risks.map((r) => (
              <tr key={r.id} className="border-b border-surface-border last:border-0">
                <td className="py-2">
                  <Link href={`/risks/${r.id}`} className="hover:underline">
                    {r.title}
                  </Link>
                </td>
                <td className="py-2">
                  <SeverityBadge band={r.residual_band} />
                </td>
                <td className="py-2 text-severity-extreme">{APPETITE_LABELS[r.appetite_status]}</td>
              </tr>
            ))}
            {data.breach_risks.length === 0 && (
              <tr>
                <td colSpan={3} className="py-6 text-center text-slate-500">
                  No risks outside appetite.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function GovernancePage() {
  return (
    <RequireAuth>
      <GovernanceHealthView />
    </RequireAuth>
  );
}

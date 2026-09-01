"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Heatmap } from "@/components/heatmap";
import { RequireAuth } from "@/components/require-auth";
import { KpiTile } from "@/components/ui/kpi-tile";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { apiFetch } from "@/lib/api";
import type { ExecutiveDashboard } from "@/lib/types";

const BAND_COLORS: Record<string, string> = {
  low: "#1a7f37",
  moderate: "#9a6700",
  high: "#bc4c00",
  extreme: "#cf222e",
};

function ExecutiveDashboardView() {
  const [data, setData] = useState<ExecutiveDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<ExecutiveDashboard>("/api/v1/dashboard/executive")
      .then(setData)
      .catch((err) => setError(String(err)));
  }, []);

  if (error) return <p className="text-sm text-severity-extreme">{error}</p>;
  if (!data) return <p className="text-sm text-slate-500">Loading…</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">Executive Dashboard</h1>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <KpiTile label="Total risks" value={data.total_risks} />
        <KpiTile label="Extreme" value={data.extreme_count} tone="extreme" />
        <KpiTile label="High" value={data.high_count} tone="high" />
        <KpiTile label="Moderate" value={data.moderate_count} tone="moderate" />
        <KpiTile label="Low" value={data.low_count} tone="low" />
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <KpiTile label="Risks outside appetite" value={data.risks_outside_appetite_count} tone="extreme" />
        <KpiTile label="Weak controls" value={data.weak_controls_count} tone="high" />
        <KpiTile label="Overdue actions" value={data.overdue_actions_count} tone="high" />
        <KpiTile label="Overdue reviews" value={data.overdue_reviews_count} tone="moderate" />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-lg border border-surface-border bg-white p-4 shadow-card">
          <h2 className="mb-3 text-sm font-semibold text-slate-900">
            5×5 Risk Heatmap (residual)
          </h2>
          <Heatmap cells={data.heatmap} />
        </div>

        <div className="rounded-lg border border-surface-border bg-white p-4 shadow-card">
          <h2 className="mb-3 text-sm font-semibold text-slate-900">
            Residual Band Distribution
          </h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data.band_distribution}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="band" tickFormatter={(v) => String(v).replace(/^\w/, (c) => c.toUpperCase())} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {data.band_distribution.map((entry) => (
                  <Cell key={entry.band} fill={BAND_COLORS[entry.band] ?? "#94a3b8"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-lg border border-surface-border bg-white p-4 shadow-card">
          <h2 className="mb-3 text-sm font-semibold text-slate-900">Risk Category Exposure</h2>
          <ResponsiveContainer width="100%" height={Math.max(220, data.category_exposure.length * 50)}>
            <BarChart data={data.category_exposure} layout="vertical" margin={{ left: 24 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" allowDecimals={false} />
              <YAxis dataKey="category_name" type="category" width={170} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="risk_count" fill="#334155" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-lg border border-surface-border bg-white p-4 shadow-card">
          <h2 className="mb-3 text-sm font-semibold text-slate-900">Risk Velocity</h2>
          {data.velocity_distribution.length === 0 ? (
            <p className="text-sm text-slate-500">No velocity data recorded yet.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {data.velocity_distribution.map((v) => (
                <li key={v.velocity} className="flex items-center justify-between">
                  <span>{v.velocity}</span>
                  <span className="font-medium text-slate-700">{v.count}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="rounded-lg border border-surface-border bg-white p-4 shadow-card">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">
          Top Risks Requiring Leadership Attention
        </h2>
        <table className="w-full text-sm">
          <thead className="border-b border-surface-border text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="py-2">Risk</th>
              <th className="py-2">Category</th>
              <th className="py-2">Residual</th>
              <th className="py-2">Owner</th>
              <th className="py-2">Next review</th>
            </tr>
          </thead>
          <tbody>
            {data.top_risks.map((risk) => (
              <tr key={risk.id} className="border-b border-surface-border last:border-0">
                <td className="py-2">
                  <Link href={`/risks/${risk.id}`} className="hover:underline">
                    {risk.title}
                  </Link>
                </td>
                <td className="py-2 text-slate-500">{risk.category_name ?? "Uncategorized"}</td>
                <td className="py-2">
                  <div className="flex items-center gap-2">
                    <span>{risk.residual_score}</span>
                    <SeverityBadge band={risk.residual_band} />
                  </div>
                </td>
                <td className="py-2 text-slate-500">{risk.owner_email ?? "Unassigned"}</td>
                <td className="py-2 text-slate-500">{risk.next_review_date ?? "—"}</td>
              </tr>
            ))}
            {data.top_risks.length === 0 && (
              <tr>
                <td colSpan={5} className="py-6 text-center text-slate-500">
                  No scored risks yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <ExecutiveDashboardView />
    </RequireAuth>
  );
}

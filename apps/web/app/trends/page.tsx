"use client";

import { useEffect, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { RequireAuth } from "@/components/require-auth";
import { KpiTile } from "@/components/ui/kpi-tile";
import { ApiError, apiFetch } from "@/lib/api";
import type { TrendPoint } from "@/lib/types";

const BAND_COLORS: Record<string, string> = {
  low: "#1a7f37",
  moderate: "#9a6700",
  high: "#bc4c00",
  extreme: "#cf222e",
};

function TrendsView() {
  const [points, setPoints] = useState<TrendPoint[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<TrendPoint[]>("/api/v1/dashboard/trends")
      .then(setPoints)
      .catch((err) => setError(err instanceof ApiError ? String(err.detail) : "Failed to load trends"));
  }, []);

  if (error) return <p className="text-sm text-severity-extreme">{error}</p>;
  if (!points) return <p className="text-sm text-slate-500">Loading…</p>;

  const latest = points[points.length - 1];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">Risk Trends</h1>
      <p className="text-sm text-slate-500">
        One point per captured snapshot, plus the current live state. Capture snapshots regularly
        (see the Snapshots page) for a meaningful trend line over time.
      </p>

      {latest && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <KpiTile label="Total risks (current)" value={latest.total_risks} />
          <KpiTile label="Extreme" value={latest.extreme} tone="extreme" />
          <KpiTile label="High" value={latest.high} tone="high" />
          <KpiTile label="Moderate" value={latest.moderate} tone="moderate" />
          <KpiTile label="Low" value={latest.low} tone="low" />
        </div>
      )}

      <div className="rounded-lg border border-surface-border bg-white p-4 shadow-card">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">Residual Band Counts Over Time</h2>
        {points.length < 2 ? (
          <p className="text-sm text-slate-500">
            Only one data point so far — capture another snapshot to see a trend line.
          </p>
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={points}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="low" name="Low" stroke={BAND_COLORS.low} strokeWidth={2} />
              <Line type="monotone" dataKey="moderate" name="Moderate" stroke={BAND_COLORS.moderate} strokeWidth={2} />
              <Line type="monotone" dataKey="high" name="High" stroke={BAND_COLORS.high} strokeWidth={2} />
              <Line type="monotone" dataKey="extreme" name="Extreme" stroke={BAND_COLORS.extreme} strokeWidth={2} />
              <Line type="monotone" dataKey="total_risks" name="Total" stroke="#334155" strokeWidth={2} strokeDasharray="4 4" />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

export default function TrendsPage() {
  return (
    <RequireAuth>
      <TrendsView />
    </RequireAuth>
  );
}

"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { useAuth } from "@/components/auth-provider";
import { RequireAuth } from "@/components/require-auth";
import { Button } from "@/components/ui/button";
import { KpiTile } from "@/components/ui/kpi-tile";
import { ApiError, apiFetch } from "@/lib/api";
import type { DistributionType, Risk, SimulationRun } from "@/lib/types";

const POLL_INTERVAL_MS = 2000;

const DISTRIBUTION_LABELS: Record<DistributionType, string> = {
  triangular: "Triangular",
  pert: "PERT (Beta-PERT)",
  lognormal: "Lognormal",
};

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function SimulationLabView() {
  const { session } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const riskIdParam = searchParams.get("risk_id");

  const [risks, setRisks] = useState<Risk[]>([]);
  const [selectedRiskId, setSelectedRiskId] = useState(riskIdParam ?? "");
  const [runs, setRuns] = useState<SimulationRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [distributionType, setDistributionType] = useState<DistributionType>("triangular");
  const [lossMin, setLossMin] = useState(1000);
  const [lossMostLikely, setLossMostLikely] = useState(10000);
  const [lossMax, setLossMax] = useState(100000);
  const [annualEventFrequency, setAnnualEventFrequency] = useState(1);
  const [iterations, setIterations] = useState(10000);
  const [seed, setSeed] = useState(42);

  const selectedRisk = risks.find((r) => r.id === selectedRiskId) ?? null;
  const canRun =
    !!selectedRisk &&
    (session?.roles.includes("risk_manager") ||
      session?.roles.includes("administrator") ||
      (session?.roles.includes("risk_owner") && selectedRisk.owner_id === session.user_id));

  useEffect(() => {
    apiFetch<Risk[]>("/api/v1/risks")
      .then(setRisks)
      .catch((err) => setError(err instanceof ApiError ? String(err.detail) : "Failed to load risks"));
  }, []);

  const loadRuns = useCallback(async (riskId: string) => {
    try {
      const data = await apiFetch<SimulationRun[]>("/api/v1/simulations", { query: { risk_id: riskId } });
      setRuns(data);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to load simulation runs");
    }
  }, []);

  useEffect(() => {
    if (selectedRiskId) loadRuns(selectedRiskId);
    else setRuns([]);
  }, [selectedRiskId, loadRuns]);

  useEffect(() => {
    const hasActive = runs.some((r) => r.status === "pending" || r.status === "running");
    if (hasActive && !pollRef.current && selectedRiskId) {
      pollRef.current = setInterval(() => loadRuns(selectedRiskId), POLL_INTERVAL_MS);
    } else if (!hasActive && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [runs, selectedRiskId, loadRuns]);

  function handleSelectRisk(riskId: string) {
    setSelectedRiskId(riskId);
    router.replace(riskId ? `/simulations?risk_id=${riskId}` : "/simulations");
  }

  async function handleRun() {
    if (!selectedRiskId) return;
    setSubmitting(true);
    setError(null);
    try {
      await apiFetch("/api/v1/simulations", {
        method: "POST",
        body: {
          risk_id: selectedRiskId,
          distribution_type: distributionType,
          loss_min: lossMin,
          loss_most_likely: lossMostLikely,
          loss_max: lossMax,
          annual_event_frequency: annualEventFrequency,
          iterations,
          seed,
        },
      });
      await loadRuns(selectedRiskId);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to start simulation");
    } finally {
      setSubmitting(false);
    }
  }

  const latestSucceeded = runs.find((r) => r.status === "succeeded" && r.result);

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">Simulation Lab</h1>
      <p className="text-sm text-slate-500">
        Risk-level Monte Carlo: models a risk&apos;s annual loss as a frequency-severity
        process — a Poisson-distributed number of loss events per year, each sized by the
        chosen distribution over your min / most likely / max estimates.
      </p>

      <div className="rounded-lg border border-surface-border bg-white p-4 shadow-card">
        <label className="block text-sm text-slate-600">
          Risk
          <select
            value={selectedRiskId}
            onChange={(e) => handleSelectRisk(e.target.value)}
            className="mt-1 block w-full max-w-xl rounded-md border border-surface-border px-2 py-1.5 text-sm"
          >
            <option value="">Select a risk…</option>
            {risks.map((r) => (
              <option key={r.id} value={r.id}>
                {r.risk_code} — {r.title}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && <p className="text-sm text-severity-extreme">{error}</p>}

      {selectedRisk && (
        <>
          {canRun ? (
            <div className="rounded-lg border border-surface-border bg-white p-4 shadow-card">
              <h2 className="mb-3 text-sm font-semibold text-slate-900">Configure &amp; run</h2>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                <label className="block text-sm text-slate-600">
                  Distribution
                  <select
                    value={distributionType}
                    onChange={(e) => setDistributionType(e.target.value as DistributionType)}
                    className="mt-1 block w-full rounded-md border border-surface-border px-2 py-1.5 text-sm"
                  >
                    {Object.entries(DISTRIBUTION_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-sm text-slate-600">
                  Annual event frequency
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    value={annualEventFrequency}
                    onChange={(e) => setAnnualEventFrequency(Number(e.target.value))}
                    className="mt-1 block w-full rounded-md border border-surface-border px-2 py-1.5 text-sm"
                  />
                </label>
                <label className="block text-sm text-slate-600">
                  Iterations
                  <input
                    type="number"
                    step="1000"
                    min="100"
                    value={iterations}
                    onChange={(e) => setIterations(Number(e.target.value))}
                    className="mt-1 block w-full rounded-md border border-surface-border px-2 py-1.5 text-sm"
                  />
                </label>
                <label className="block text-sm text-slate-600">
                  Loss — minimum ($)
                  <input
                    type="number"
                    min="0"
                    value={lossMin}
                    onChange={(e) => setLossMin(Number(e.target.value))}
                    className="mt-1 block w-full rounded-md border border-surface-border px-2 py-1.5 text-sm"
                  />
                </label>
                <label className="block text-sm text-slate-600">
                  Loss — most likely ($)
                  <input
                    type="number"
                    min="0"
                    value={lossMostLikely}
                    onChange={(e) => setLossMostLikely(Number(e.target.value))}
                    className="mt-1 block w-full rounded-md border border-surface-border px-2 py-1.5 text-sm"
                  />
                </label>
                <label className="block text-sm text-slate-600">
                  Loss — maximum ($)
                  <input
                    type="number"
                    min="0"
                    value={lossMax}
                    onChange={(e) => setLossMax(Number(e.target.value))}
                    className="mt-1 block w-full rounded-md border border-surface-border px-2 py-1.5 text-sm"
                  />
                </label>
                <label className="block text-sm text-slate-600">
                  Seed (reproducibility)
                  <input
                    type="number"
                    value={seed}
                    onChange={(e) => setSeed(Number(e.target.value))}
                    className="mt-1 block w-full rounded-md border border-surface-border px-2 py-1.5 text-sm"
                  />
                </label>
              </div>
              <div className="mt-4">
                <Button onClick={handleRun} disabled={submitting}>
                  {submitting ? "Starting…" : "Run simulation"}
                </Button>
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">
              You don&apos;t have permission to run a simulation for this risk.
            </p>
          )}

          {latestSucceeded?.result && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                <KpiTile
                  label="Expected annual loss"
                  value={formatCurrency(latestSucceeded.result.expected_annual_loss)}
                />
                <KpiTile label="Median" value={formatCurrency(latestSucceeded.result.median)} />
                <KpiTile label="P90" value={formatCurrency(latestSucceeded.result.p90)} />
                <KpiTile label="P95" value={formatCurrency(latestSucceeded.result.p95)} tone="moderate" />
                <KpiTile label="P99" value={formatCurrency(latestSucceeded.result.p99)} tone="high" />
              </div>
              <div className="rounded-lg border border-surface-border bg-white p-4 shadow-card">
                <h2 className="mb-3 text-sm font-semibold text-slate-900">
                  Simulated Annual Loss Distribution
                </h2>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart
                    data={latestSucceeded.result.histogram.map((b) => ({
                      label: formatCurrency(b.bin_start),
                      count: b.count,
                    }))}
                  >
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="label" tick={{ fontSize: 10 }} angle={-40} textAnchor="end" height={70} />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#334155" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          <div className="rounded-lg border border-surface-border bg-white p-4 shadow-card">
            <h2 className="mb-3 text-sm font-semibold text-slate-900">Run History</h2>
            <table className="w-full text-sm">
              <thead className="border-b border-surface-border text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-2">Requested</th>
                  <th className="py-2">Distribution</th>
                  <th className="py-2">Iterations</th>
                  <th className="py-2">Status</th>
                  <th className="py-2">Expected annual loss</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id} className="border-b border-surface-border last:border-0">
                    <td className="py-2 text-slate-500">{new Date(run.created_at).toLocaleString()}</td>
                    <td className="py-2 capitalize">{run.config?.distribution_type ?? "—"}</td>
                    <td className="py-2">{run.iterations_used.toLocaleString()}</td>
                    <td className="py-2 capitalize">
                      {run.status}
                      {run.status === "failed" && run.error ? ` — ${run.error}` : ""}
                    </td>
                    <td className="py-2">
                      {run.result ? formatCurrency(run.result.expected_annual_loss) : "—"}
                    </td>
                  </tr>
                ))}
                {runs.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-6 text-center text-slate-500">
                      No simulations run yet for this risk.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

export default function SimulationsPage() {
  return (
    <RequireAuth>
      <Suspense fallback={<p className="text-sm text-slate-500">Loading…</p>}>
        <SimulationLabView />
      </Suspense>
    </RequireAuth>
  );
}

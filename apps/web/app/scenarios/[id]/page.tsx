"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { useAuth } from "@/components/auth-provider";
import { RequireAuth } from "@/components/require-auth";
import { Button } from "@/components/ui/button";
import { KpiTile } from "@/components/ui/kpi-tile";
import { ApiError, apiFetch } from "@/lib/api";
import type { Risk, Scenario, ScenarioExposure, SimulationRun } from "@/lib/types";

const POLL_INTERVAL_MS = 2000;

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function ScenarioDetail({ id }: { id: string }) {
  const { session } = useAuth();
  const canManage = session?.roles.includes("risk_manager") || session?.roles.includes("administrator");

  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [exposure, setExposure] = useState<ScenarioExposure | null>(null);
  const [allRisks, setAllRisks] = useState<Risk[]>([]);
  const [selectedRiskId, setSelectedRiskId] = useState("");
  const [run, setRun] = useState<SimulationRun | null>(null);
  const [iterations, setIterations] = useState(10000);
  const [seed, setSeed] = useState(42);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const riskById = new Map(allRisks.map((r) => [r.id, r]));

  const load = useCallback(async () => {
    try {
      const [scenarioData, exposureData, risksData] = await Promise.all([
        apiFetch<Scenario>(`/api/v1/scenarios/${id}`),
        apiFetch<ScenarioExposure>(`/api/v1/scenarios/${id}/exposure`),
        apiFetch<Risk[]>("/api/v1/risks"),
      ]);
      setScenario(scenarioData);
      setExposure(exposureData);
      setAllRisks(risksData);
      if (exposureData.latest_run_id) {
        const latestRun = await apiFetch<SimulationRun>(`/api/v1/simulations/${exposureData.latest_run_id}`);
        setRun(latestRun);
      }
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to load scenario");
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const isActive = run?.status === "pending" || run?.status === "running";
    if (isActive && !pollRef.current) {
      pollRef.current = setInterval(async () => {
        const updated = await apiFetch<SimulationRun>(`/api/v1/simulations/${run!.id}`);
        setRun(updated);
      }, POLL_INTERVAL_MS);
    } else if (!isActive && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [run]);

  const linkableRisks = allRisks.filter((r) => !scenario?.linked_risk_ids.includes(r.id));

  async function handleLink() {
    if (!selectedRiskId) return;
    try {
      await apiFetch(`/api/v1/scenarios/${id}/risks`, { method: "POST", query: { risk_id: selectedRiskId } });
      setSelectedRiskId("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to link risk");
    }
  }

  async function handleUnlink(riskId: string) {
    try {
      await apiFetch(`/api/v1/scenarios/${id}/risks/${riskId}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to unlink risk");
    }
  }

  async function handleRunPortfolio() {
    setRunning(true);
    setError(null);
    try {
      const newRun = await apiFetch<SimulationRun>("/api/v1/simulations/portfolio", {
        method: "POST",
        body: { scenario_id: id, iterations, seed },
      });
      setRun(newRun);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to start portfolio simulation");
    } finally {
      setRunning(false);
    }
  }

  if (error && !scenario) return <p className="text-sm text-severity-extreme">{error}</p>;
  if (!scenario) return <p className="text-sm text-slate-500">Loading…</p>;

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <Link href="/scenarios" className="text-xs text-slate-500 hover:underline">
          ← Scenarios
        </Link>
        <h1 className="text-xl font-semibold text-slate-900">{scenario.name}</h1>
        {scenario.description && <p className="mt-1 text-sm text-slate-600">{scenario.description}</p>}
      </div>

      {error && <p className="text-sm text-severity-extreme">{error}</p>}

      <div className="rounded-lg border border-surface-border bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">Linked Risks</h2>
        <ul className="mb-3 space-y-1 text-sm">
          {scenario.linked_risk_ids.map((riskId) => {
            const risk = riskById.get(riskId);
            const missingConfig = exposure?.risks_missing_simulation_config.includes(riskId);
            return (
              <li key={riskId} className="flex items-center justify-between">
                <Link href={`/risks/${riskId}`} className="hover:underline">
                  {risk ? `${risk.risk_code} — ${risk.title}` : riskId}
                </Link>
                <div className="flex items-center gap-3">
                  {missingConfig && (
                    <Link
                      href={`/simulations?risk_id=${riskId}`}
                      className="text-xs text-severity-high hover:underline"
                    >
                      No simulation config — configure it
                    </Link>
                  )}
                  {canManage && (
                    <button
                      onClick={() => handleUnlink(riskId)}
                      className="text-xs text-slate-400 hover:text-severity-extreme"
                    >
                      Unlink
                    </button>
                  )}
                </div>
              </li>
            );
          })}
          {scenario.linked_risk_ids.length === 0 && <li className="text-slate-500">No risks linked yet.</li>}
        </ul>
        {canManage && (
          <div className="flex gap-2">
            <select
              value={selectedRiskId}
              onChange={(e) => setSelectedRiskId(e.target.value)}
              className="flex-1 rounded-md border border-surface-border px-2 py-1.5 text-sm"
            >
              <option value="">Select a risk to link…</option>
              {linkableRisks.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.risk_code} — {r.title}
                </option>
              ))}
            </select>
            <Button variant="secondary" onClick={handleLink} disabled={!selectedRiskId}>
              Link
            </Button>
          </div>
        )}
      </div>

      {canManage && (
        <div className="rounded-lg border border-surface-border bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-900">Portfolio Monte Carlo</h2>
          <p className="mb-3 text-sm text-slate-500">
            Runs every linked risk&apos;s own configured frequency-severity model together,
            correlating risks that share a correlation group (set on each risk&apos;s
            simulation config), and reports the combined exposure plus each risk&apos;s share
            of the tail (worst 5%) outcomes.
          </p>
          <div className="mb-3 flex gap-4">
            <label className="block text-sm text-slate-600">
              Iterations
              <input
                type="number"
                step="1000"
                min="100"
                value={iterations}
                onChange={(e) => setIterations(Number(e.target.value))}
                className="mt-1 block w-32 rounded-md border border-surface-border px-2 py-1.5 text-sm"
              />
            </label>
            <label className="block text-sm text-slate-600">
              Seed
              <input
                type="number"
                value={seed}
                onChange={(e) => setSeed(Number(e.target.value))}
                className="mt-1 block w-32 rounded-md border border-surface-border px-2 py-1.5 text-sm"
              />
            </label>
          </div>
          <Button
            onClick={handleRunPortfolio}
            disabled={running || scenario.linked_risk_ids.length === 0}
          >
            {running ? "Starting…" : "Run portfolio simulation"}
          </Button>
        </div>
      )}

      {run && (
        <div className="space-y-4">
          <div className="rounded-lg border border-surface-border bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-slate-900">
              Latest Run — <span className="capitalize">{run.status}</span>
            </h2>
            {run.status === "failed" && <p className="text-sm text-severity-extreme">{run.error}</p>}
            {run.result && (
              <>
                <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
                  <KpiTile label="Expected annual loss" value={formatCurrency(run.result.expected_annual_loss)} />
                  <KpiTile label="Median" value={formatCurrency(run.result.median)} />
                  <KpiTile label="P90" value={formatCurrency(run.result.p90)} />
                  <KpiTile label="P95" value={formatCurrency(run.result.p95)} tone="moderate" />
                  <KpiTile label="P99" value={formatCurrency(run.result.p99)} tone="high" />
                </div>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart
                    data={run.result.histogram.map((b) => ({ label: formatCurrency(b.bin_start), count: b.count }))}
                  >
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="label" tick={{ fontSize: 10 }} angle={-40} textAnchor="end" height={70} />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#334155" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </>
            )}
          </div>

          {run.result?.per_risk_contribution && (
            <div className="rounded-lg border border-surface-border bg-white p-4">
              <h2 className="mb-3 text-sm font-semibold text-slate-900">
                Tail-Risk Contribution (worst 5% of portfolio outcomes)
              </h2>
              <table className="w-full text-sm">
                <thead className="border-b border-surface-border text-left text-xs uppercase text-slate-500">
                  <tr>
                    <th className="py-2">Risk</th>
                    <th className="py-2">Share of tail loss</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(run.result.per_risk_contribution)
                    .sort((a, b) => b[1] - a[1])
                    .map(([riskId, fraction]) => (
                      <tr key={riskId} className="border-b border-surface-border last:border-0">
                        <td className="py-2">
                          <Link href={`/risks/${riskId}`} className="hover:underline">
                            {riskById.get(riskId)?.title ?? riskId}
                          </Link>
                        </td>
                        <td className="py-2">{(fraction * 100).toFixed(1)}%</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ScenarioDetailPage() {
  const params = useParams<{ id: string }>();
  return (
    <RequireAuth>
      <ScenarioDetail id={params.id} />
    </RequireAuth>
  );
}

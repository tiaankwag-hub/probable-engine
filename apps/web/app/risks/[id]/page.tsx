"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ImpactScoresInput } from "@/components/impact-scores-input";
import { RequireAuth } from "@/components/require-auth";
import { Button } from "@/components/ui/button";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { ApiError, apiFetch } from "@/lib/api";
import type { ImpactScores, Risk, RiskHistoryEntry } from "@/lib/types";

const DEFAULT_SCORES: ImpactScores = {
  financial: 3,
  customer_service: 3,
  operational_delivery: 3,
  legal_regulatory: 3,
  reputation: 3,
  health_safety: 3,
};

function RiskDetail({ id }: { id: string }) {
  const [risk, setRisk] = useState<Risk | null>(null);
  const [history, setHistory] = useState<RiskHistoryEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [reassessing, setReassessing] = useState(false);
  const [scores, setScores] = useState<ImpactScores>(DEFAULT_SCORES);
  const [likelihood, setLikelihood] = useState(3);
  const [controlEffectiveness, setControlEffectiveness] = useState<number | "">(3);

  async function load() {
    try {
      const [riskData, historyData] = await Promise.all([
        apiFetch<Risk>(`/api/v1/risks/${id}`),
        apiFetch<RiskHistoryEntry[]>(`/api/v1/risks/${id}/history`),
      ]);
      setRisk(riskData);
      setHistory(historyData);
      setLikelihood(riskData.likelihood ?? 3);
      setControlEffectiveness(riskData.control_effectiveness ?? "");
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to load risk");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleReassess() {
    if (!risk) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await apiFetch<Risk>(`/api/v1/risks/${id}`, {
        method: "PATCH",
        body: {
          version: risk.version,
          assessment: {
            likelihood,
            impact_scores: scores,
            control_effectiveness: controlEffectiveness === "" ? null : controlEffectiveness,
          },
        },
      });
      setRisk(updated);
      setReassessing(false);
      await load();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("This risk changed since you loaded it. Reloading latest version…");
        await load();
      } else {
        setError(err instanceof ApiError ? String(err.detail) : "Failed to save assessment");
      }
    } finally {
      setSaving(false);
    }
  }

  if (error && !risk) return <p className="text-sm text-severity-extreme">{error}</p>;
  if (!risk) return <p className="text-sm text-slate-500">Loading…</p>;

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <p className="font-mono text-xs text-slate-500">{risk.risk_code}</p>
        <h1 className="text-xl font-semibold text-slate-900">{risk.title}</h1>
        {risk.statement && <p className="mt-1 text-sm text-slate-600">{risk.statement}</p>}
      </div>

      <div className="grid grid-cols-2 gap-4 rounded-lg border border-surface-border bg-white p-4 sm:grid-cols-4">
        <div>
          <p className="text-xs uppercase text-slate-500">Status</p>
          <p className="text-sm capitalize">{risk.status}</p>
        </div>
        <div>
          <p className="text-xs uppercase text-slate-500">Decision</p>
          <p className="text-sm capitalize">{risk.decision}</p>
        </div>
        <div>
          <p className="text-xs uppercase text-slate-500">Inherent</p>
          <div className="mt-1 flex items-center gap-2">
            <span className="text-sm">{risk.inherent_score ?? "—"}</span>
            <SeverityBadge band={risk.inherent_band} />
          </div>
        </div>
        <div>
          <p className="text-xs uppercase text-slate-500">Residual</p>
          <div className="mt-1 flex items-center gap-2">
            <span className="text-sm">{risk.residual_score ?? "—"}</span>
            <SeverityBadge band={risk.residual_band} />
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-surface-border bg-white p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-900">Assessment</h2>
          {!reassessing && (
            <Button variant="secondary" onClick={() => setReassessing(true)}>
              Record new assessment
            </Button>
          )}
        </div>

        {!reassessing ? (
          <p className="text-sm text-slate-500">
            Likelihood {risk.likelihood ?? "—"} · Overall impact {risk.overall_impact ?? "—"} ·
            Control effectiveness {risk.control_effectiveness ?? "—"}
          </p>
        ) : (
          <div className="space-y-4">
            <ImpactScoresInput value={scores} onChange={setScores} />
            <div className="grid grid-cols-2 gap-4">
              <label className="block text-sm text-slate-600">
                Likelihood
                <select
                  value={likelihood}
                  onChange={(e) => setLikelihood(Number(e.target.value))}
                  className="mt-1 block w-full rounded-md border border-surface-border px-2 py-1.5 text-sm"
                >
                  {[1, 2, 3, 4, 5].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm text-slate-600">
                Control effectiveness
                <select
                  value={controlEffectiveness}
                  onChange={(e) =>
                    setControlEffectiveness(e.target.value === "" ? "" : Number(e.target.value))
                  }
                  className="mt-1 block w-full rounded-md border border-surface-border px-2 py-1.5 text-sm"
                >
                  <option value="">No controls assessed</option>
                  {[1, 2, 3, 4, 5].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="flex gap-2">
              <Button onClick={handleReassess} disabled={saving}>
                {saving ? "Saving…" : "Save assessment"}
              </Button>
              <Button variant="ghost" onClick={() => setReassessing(false)}>
                Cancel
              </Button>
            </div>
          </div>
        )}
        {error && <p className="mt-2 text-sm text-severity-extreme">{error}</p>}
      </div>

      <div className="rounded-lg border border-surface-border bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">History</h2>
        <ul className="space-y-2 text-sm">
          {history.map((entry) => (
            <li key={entry.id} className="border-b border-surface-border pb-2 last:border-0">
              <span className="font-mono text-xs text-slate-500">v{entry.version}</span>{" "}
              <span className="text-slate-700">{String(entry.field_state.title)}</span>{" "}
              <span className="text-slate-400">
                — {entry.actor ?? "unknown"} at {new Date(entry.recorded_at).toLocaleString()}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default function RiskDetailPage() {
  const params = useParams<{ id: string }>();
  return (
    <RequireAuth>
      <RiskDetail id={params.id} />
    </RequireAuth>
  );
}

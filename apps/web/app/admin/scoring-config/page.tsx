"use client";

import { FormEvent, useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { RequireAuth } from "@/components/require-auth";
import { Button } from "@/components/ui/button";
import { ApiError, apiFetch } from "@/lib/api";
import type { ScoringConfig } from "@/lib/types";

const DIMENSIONS: { key: string; label: string }[] = [
  { key: "financial", label: "Financial" },
  { key: "customer_service", label: "Customer / Service" },
  { key: "operational_delivery", label: "Operational Delivery" },
  { key: "legal_regulatory", label: "Legal / Regulatory" },
  { key: "reputation", label: "Reputation" },
  { key: "health_safety", label: "Health & Safety" },
];

function equalWeights(): Record<string, number> {
  const w = Math.round((1 / DIMENSIONS.length) * 10000) / 10000;
  return Object.fromEntries(DIMENSIONS.map((d) => [d.key, w]));
}

function ScoringConfigAdmin() {
  const { session } = useAuth();
  const isAdministrator = session?.roles.includes("administrator") ?? false;

  const [configs, setConfigs] = useState<ScoringConfig[]>([]);
  const [weights, setWeights] = useState<Record<string, number>>(equalWeights());
  const [thresholds, setThresholds] = useState<[number, string][]>([
    [6, "low"],
    [12, "moderate"],
    [18, "high"],
    [25, "extreme"],
  ]);
  const [maxReduction, setMaxReduction] = useState(0.6);
  const [maxControlEffectiveness, setMaxControlEffectiveness] = useState(5);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function load() {
    apiFetch<ScoringConfig[]>("/api/v1/scoring-config").then(setConfigs).catch(() => {});
  }

  useEffect(load, []);

  const weightSum = Object.values(weights).reduce((a, b) => a + b, 0);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await apiFetch("/api/v1/scoring-config", {
        method: "POST",
        body: {
          dimension_weights: weights,
          band_thresholds: thresholds,
          max_reduction_fraction: maxReduction,
          max_control_effectiveness: maxControlEffectiveness,
        },
      });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to save scoring config");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Scoring Configuration</h1>
        <p className="mt-1 text-sm text-slate-500">
          Impact-dimension weights and band thresholds are stored here, not hard-coded (ADR
          0007). Every past assessment keeps referencing the config version active when it was
          computed, so changing this never rewrites history.
        </p>
      </div>

      <div className="rounded-lg border border-surface-border bg-white p-4 shadow-card">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">Version history</h2>
        <table className="w-full text-sm">
          <thead className="border-b border-surface-border text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="py-2">Version</th>
              <th className="py-2">Active</th>
              <th className="py-2">Created</th>
            </tr>
          </thead>
          <tbody>
            {configs.map((c) => (
              <tr key={c.id} className="border-b border-surface-border last:border-0">
                <td className="py-2">v{c.version}</td>
                <td className="py-2">{c.is_active ? "Yes" : "No"}</td>
                <td className="py-2 text-slate-500">{new Date(c.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {!isAdministrator ? (
        <p className="text-sm text-slate-500">
          Only Administrators can create a new scoring configuration version.
        </p>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5 rounded-lg border border-surface-border bg-white p-4 shadow-card">
          <h2 className="text-sm font-semibold text-slate-900">Publish a new version</h2>

          <div>
            <p className="mb-2 text-sm font-medium text-slate-700">
              Dimension weights (must sum to 1.0 — currently {weightSum.toFixed(3)})
            </p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {DIMENSIONS.map((dim) => (
                <label key={dim.key} className="text-sm text-slate-600">
                  {dim.label}
                  <input
                    type="number"
                    step="any"
                    min="0"
                    max="1"
                    value={weights[dim.key]}
                    onChange={(e) =>
                      setWeights({ ...weights, [dim.key]: Number(e.target.value) })
                    }
                    className="mt-1 block w-full rounded-md border border-surface-border px-2 py-1.5 text-sm"
                  />
                </label>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-2 text-sm font-medium text-slate-700">
              Band thresholds (ascending upper bound → band name)
            </p>
            <div className="space-y-2">
              {thresholds.map(([bound, band], idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <input
                    type="number"
                    step="0.5"
                    value={bound}
                    onChange={(e) => {
                      const next = [...thresholds] as [number, string][];
                      next[idx] = [Number(e.target.value), band];
                      setThresholds(next);
                    }}
                    className="w-24 rounded-md border border-surface-border px-2 py-1.5 text-sm"
                  />
                  <span className="text-sm text-slate-500">→</span>
                  <input
                    value={band}
                    onChange={(e) => {
                      const next = [...thresholds] as [number, string][];
                      next[idx] = [bound, e.target.value];
                      setThresholds(next);
                    }}
                    className="w-32 rounded-md border border-surface-border px-2 py-1.5 text-sm"
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <label className="text-sm text-slate-600">
              Max control-reduction fraction
              <input
                type="number"
                step="0.05"
                min="0"
                max="1"
                value={maxReduction}
                onChange={(e) => setMaxReduction(Number(e.target.value))}
                className="mt-1 block w-full rounded-md border border-surface-border px-2 py-1.5 text-sm"
              />
            </label>
            <label className="text-sm text-slate-600">
              Max control-effectiveness scale
              <input
                type="number"
                min="1"
                value={maxControlEffectiveness}
                onChange={(e) => setMaxControlEffectiveness(Number(e.target.value))}
                className="mt-1 block w-full rounded-md border border-surface-border px-2 py-1.5 text-sm"
              />
            </label>
          </div>

          {error && <p className="text-sm text-severity-extreme">{error}</p>}

          <Button type="submit" disabled={submitting}>
            {submitting ? "Publishing…" : "Publish new version"}
          </Button>
        </form>
      )}
    </div>
  );
}

export default function ScoringConfigPage() {
  return (
    <RequireAuth>
      <ScoringConfigAdmin />
    </RequireAuth>
  );
}

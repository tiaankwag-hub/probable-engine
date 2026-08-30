"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { ImpactScoresInput } from "@/components/impact-scores-input";
import { RequireAuth } from "@/components/require-auth";
import { Button } from "@/components/ui/button";
import { ApiError, apiFetch } from "@/lib/api";
import type { ImpactScores, Risk, RiskCategory, RiskDecision, RiskStatus } from "@/lib/types";

const DEFAULT_SCORES: ImpactScores = {
  financial: 1,
  customer_service: 1,
  operational_delivery: 1,
  legal_regulatory: 1,
  reputation: 1,
  health_safety: 1,
};

function NewRiskForm() {
  const router = useRouter();
  const [categories, setCategories] = useState<RiskCategory[]>([]);
  const [title, setTitle] = useState("");
  const [statement, setStatement] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [department, setDepartment] = useState("");
  const [status, setStatus] = useState<RiskStatus>("draft");
  const [decision, setDecision] = useState<RiskDecision>("pending");
  const [acceptanceRationale, setAcceptanceRationale] = useState("");
  const [likelihood, setLikelihood] = useState(3);
  const [controlEffectiveness, setControlEffectiveness] = useState<number | "">(3);
  const [scores, setScores] = useState<ImpactScores>(DEFAULT_SCORES);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    apiFetch<RiskCategory[]>("/api/v1/risk-categories").then(setCategories).catch(() => {});
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (decision === "accept" && !acceptanceRationale.trim()) {
      setError("Acceptance rationale is required when decision is 'accept'.");
      return;
    }
    setSubmitting(true);
    try {
      const risk = await apiFetch<Risk>("/api/v1/risks", {
        method: "POST",
        body: {
          title,
          statement: statement || null,
          category_id: categoryId || null,
          department: department || null,
          status,
          decision,
          acceptance_rationale: acceptanceRationale || null,
          assessment: {
            likelihood,
            impact_scores: scores,
            control_effectiveness: controlEffectiveness === "" ? null : controlEffectiveness,
          },
        },
      });
      router.push(`/risks/${risk.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to create risk");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-2xl space-y-5">
      <h1 className="text-xl font-semibold text-slate-900">New risk</h1>

      <label className="block text-sm text-slate-600">
        Title
        <input
          required
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="mt-1 block w-full rounded-md border border-surface-border px-3 py-2 text-sm"
        />
      </label>

      <label className="block text-sm text-slate-600">
        Statement (cause / event / impact)
        <textarea
          value={statement}
          onChange={(e) => setStatement(e.target.value)}
          rows={3}
          className="mt-1 block w-full rounded-md border border-surface-border px-3 py-2 text-sm"
        />
      </label>

      <div className="grid grid-cols-2 gap-4">
        <label className="block text-sm text-slate-600">
          Category
          <select
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
            className="mt-1 block w-full rounded-md border border-surface-border px-3 py-2 text-sm"
          >
            <option value="">Unassigned</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm text-slate-600">
          Department
          <input
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
            className="mt-1 block w-full rounded-md border border-surface-border px-3 py-2 text-sm"
          />
        </label>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <label className="block text-sm text-slate-600">
          Status
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as RiskStatus)}
            className="mt-1 block w-full rounded-md border border-surface-border px-3 py-2 text-sm"
          >
            <option value="draft">Draft</option>
            <option value="open">Open</option>
            <option value="monitoring">Monitoring</option>
            <option value="closed">Closed</option>
          </select>
        </label>
        <label className="block text-sm text-slate-600">
          Decision
          <select
            value={decision}
            onChange={(e) => setDecision(e.target.value as RiskDecision)}
            className="mt-1 block w-full rounded-md border border-surface-border px-3 py-2 text-sm"
          >
            <option value="pending">Pending</option>
            <option value="treat">Treat</option>
            <option value="accept">Accept</option>
            <option value="transfer">Transfer</option>
            <option value="avoid">Avoid</option>
          </select>
        </label>
      </div>

      {decision === "accept" && (
        <label className="block text-sm text-slate-600">
          Acceptance rationale (required)
          <textarea
            value={acceptanceRationale}
            onChange={(e) => setAcceptanceRationale(e.target.value)}
            rows={2}
            className="mt-1 block w-full rounded-md border border-surface-border px-3 py-2 text-sm"
          />
        </label>
      )}

      <div>
        <p className="mb-2 text-sm font-medium text-slate-700">Impact assessment (1–5)</p>
        <ImpactScoresInput value={scores} onChange={setScores} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <label className="block text-sm text-slate-600">
          Likelihood (12-month horizon)
          <select
            value={likelihood}
            onChange={(e) => setLikelihood(Number(e.target.value))}
            className="mt-1 block w-full rounded-md border border-surface-border px-3 py-2 text-sm"
          >
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm text-slate-600">
          Control effectiveness (optional)
          <select
            value={controlEffectiveness}
            onChange={(e) =>
              setControlEffectiveness(e.target.value === "" ? "" : Number(e.target.value))
            }
            className="mt-1 block w-full rounded-md border border-surface-border px-3 py-2 text-sm"
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

      {error && <p className="text-sm text-severity-extreme">{error}</p>}

      <Button type="submit" disabled={submitting}>
        {submitting ? "Creating…" : "Create risk"}
      </Button>
    </form>
  );
}

export default function NewRiskPage() {
  return (
    <RequireAuth>
      <NewRiskForm />
    </RequireAuth>
  );
}

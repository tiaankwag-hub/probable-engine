"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { ImpactScoresInput } from "@/components/impact-scores-input";
import { RequireAuth } from "@/components/require-auth";
import { Button } from "@/components/ui/button";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { ApiError, apiFetch } from "@/lib/api";
import type {
  Action,
  AIRun,
  AISuggestion,
  Control,
  ImpactScores,
  Incident,
  IncidentSeverity,
  Issue,
  Risk,
  RiskHistoryEntry,
} from "@/lib/types";

const AI_POLL_INTERVAL_MS = 2000;

function RiskAiAnalysisPanel({
  riskId,
  isOwnRisk,
  onRiskChanged,
}: {
  riskId: string;
  isOwnRisk: boolean;
  onRiskChanged: () => void;
}) {
  const { session } = useAuth();
  const canAnalyze =
    session?.roles.includes("risk_manager") ||
    session?.roles.includes("administrator") ||
    (session?.roles.includes("risk_owner") && isOwnRisk);
  const canView = canAnalyze || session?.roles.includes("executive");
  const canReview = session?.roles.includes("risk_manager") || session?.roles.includes("administrator");

  const [run, setRun] = useState<AIRun | null>(null);
  const [suggestions, setSuggestions] = useState<AISuggestion[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [requesting, setRequesting] = useState(false);
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function loadSuggestions() {
    try {
      setSuggestions(await apiFetch<AISuggestion[]>("/api/v1/ai/suggestions", { query: { risk_id: riskId } }));
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to load AI suggestions");
    }
  }

  useEffect(() => {
    if (canView) loadSuggestions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canView]);

  useEffect(() => {
    const isActive = run?.status === "pending" || run?.status === "running";
    if (isActive && !pollRef.current) {
      pollRef.current = setInterval(async () => {
        try {
          const updated = await apiFetch<AIRun>(`/api/v1/ai/runs/${run!.id}`);
          setRun(updated);
          if (updated.status === "succeeded") await loadSuggestions();
        } catch (err) {
          setError(err instanceof ApiError ? String(err.detail) : "Failed to poll AI analysis");
        }
      }, AI_POLL_INTERVAL_MS);
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run]);

  async function handleRequest() {
    setRequesting(true);
    setError(null);
    try {
      const newRun = await apiFetch<AIRun>("/api/v1/ai/risk-analysis", {
        method: "POST",
        body: { risk_id: riskId },
      });
      setRun(newRun);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to request AI analysis");
    } finally {
      setRequesting(false);
    }
  }

  async function handleDecision(suggestionId: string, action: "approve" | "reject") {
    setReviewingId(suggestionId);
    try {
      await apiFetch(`/api/v1/ai/suggestions/${suggestionId}/${action}`, { method: "POST" });
      await loadSuggestions();
      if (action === "approve") onRiskChanged();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : `Failed to ${action} suggestion`);
    } finally {
      setReviewingId(null);
    }
  }

  if (!canView) return null;

  return (
    <div className="rounded-lg border border-surface-border bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900">AI Analysis</h2>
        {canAnalyze && (
          <Button
            variant="secondary"
            onClick={handleRequest}
            disabled={requesting || run?.status === "pending" || run?.status === "running"}
          >
            {requesting ? "Requesting…" : "Request AI analysis"}
          </Button>
        )}
      </div>
      {error && <p className="text-sm text-severity-extreme">{error}</p>}
      {run && (run.status === "pending" || run.status === "running") && (
        <p className="text-sm text-slate-500">Analyzing…</p>
      )}
      {run?.status === "failed" && <p className="text-sm text-severity-extreme">{run.error}</p>}
      {run?.status === "succeeded" && (
        <div className="mb-3">
          <p className="text-sm text-slate-700">{run.narrative}</p>
          <p className="mt-1 text-xs text-slate-400">AI-generated · model: {run.model}</p>
        </div>
      )}
      {suggestions.map((s) => (
        <div key={s.id} className="mt-3 rounded-md border border-surface-border p-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">{s.summary}</span>
            <span className="text-xs capitalize text-slate-500">{s.human_review_status}</span>
          </div>
          <p className="mt-1 text-sm text-slate-600">{s.rationale}</p>
          <p className="mt-1 text-xs text-slate-400">
            Proposed: {Object.entries(s.proposed_changes).map(([k, v]) => `${k} → ${v}`).join(", ")}
          </p>
          {s.human_review_status === "pending" && (
            canReview ? (
              <div className="mt-2 flex gap-2">
                <Button
                  variant="secondary"
                  onClick={() => handleDecision(s.id, "approve")}
                  disabled={reviewingId !== null}
                >
                  {reviewingId === s.id ? "Approving…" : "Approve"}
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => handleDecision(s.id, "reject")}
                  disabled={reviewingId !== null}
                >
                  Reject
                </Button>
              </div>
            ) : (
              <p className="mt-2 text-xs text-slate-400">
                Awaiting review by a Risk Manager or Administrator.
              </p>
            )
          )}
        </div>
      ))}
      {!run && suggestions.length === 0 && (
        <p className="text-sm text-slate-500">No AI analysis requested yet for this risk.</p>
      )}
    </div>
  );
}

const APPETITE_LABELS: Record<string, string> = {
  within_appetite: "Within appetite",
  approaching_tolerance: "Approaching tolerance",
  outside_appetite: "Outside appetite",
  material_breach: "Material breach",
  not_configured: "Appetite not configured",
};

const APPETITE_TONE: Record<string, string> = {
  within_appetite: "text-severity-low",
  approaching_tolerance: "text-severity-moderate",
  outside_appetite: "text-severity-high",
  material_breach: "text-severity-extreme",
  not_configured: "text-slate-400",
};

const DEFAULT_SCORES: ImpactScores = {
  financial: 3,
  customer_service: 3,
  operational_delivery: 3,
  legal_regulatory: 3,
  reputation: 3,
  health_safety: 3,
};

function RiskDetail({ id }: { id: string }) {
  const { session } = useAuth();
  const canTriggerReview =
    session?.roles.includes("risk_manager") || session?.roles.includes("administrator");

  const [risk, setRisk] = useState<Risk | null>(null);
  const [history, setHistory] = useState<RiskHistoryEntry[]>([]);
  const [controls, setControls] = useState<Control[]>([]);
  const [allControls, setAllControls] = useState<Control[]>([]);
  const [actions, setActions] = useState<Action[]>([]);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [reassessing, setReassessing] = useState(false);
  const [scores, setScores] = useState<ImpactScores>(DEFAULT_SCORES);
  const [likelihood, setLikelihood] = useState(3);
  const [controlEffectiveness, setControlEffectiveness] = useState<number | "">(3);
  const [selectedControlId, setSelectedControlId] = useState("");
  const [newActionTitle, setNewActionTitle] = useState("");
  const [newIssueDescription, setNewIssueDescription] = useState("");
  const [newIncidentDescription, setNewIncidentDescription] = useState("");
  const [newIncidentSeverity, setNewIncidentSeverity] = useState<IncidentSeverity>("moderate");

  async function load() {
    try {
      const [riskData, historyData, controlsData, allControlsData, actionsData, issuesData, incidentsData] =
        await Promise.all([
          apiFetch<Risk>(`/api/v1/risks/${id}`),
          apiFetch<RiskHistoryEntry[]>(`/api/v1/risks/${id}/history`),
          apiFetch<Control[]>(`/api/v1/risks/${id}/controls`),
          apiFetch<Control[]>("/api/v1/controls"),
          apiFetch<Action[]>(`/api/v1/risks/${id}/actions`),
          apiFetch<Issue[]>(`/api/v1/risks/${id}/issues`),
          apiFetch<Incident[]>(`/api/v1/risks/${id}/incidents`),
        ]);
      setRisk(riskData);
      setHistory(historyData);
      setControls(controlsData);
      setAllControls(allControlsData);
      setActions(actionsData);
      setIssues(issuesData);
      setIncidents(incidentsData);
      setLikelihood(riskData.likelihood ?? 3);
      setControlEffectiveness(riskData.control_effectiveness ?? "");
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to load risk");
    }
  }

  async function handleCreateIssue() {
    if (!newIssueDescription.trim()) return;
    try {
      await apiFetch("/api/v1/issues", {
        method: "POST",
        body: { risk_id: id, description: newIssueDescription },
      });
      setNewIssueDescription("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to create issue");
    }
  }

  async function handleCreateIncident() {
    if (!newIncidentDescription.trim()) return;
    try {
      await apiFetch("/api/v1/incidents", {
        method: "POST",
        body: {
          risk_id: id,
          description: newIncidentDescription,
          incident_date: new Date().toISOString().slice(0, 10),
          severity: newIncidentSeverity,
        },
      });
      setNewIncidentDescription("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to create incident");
    }
  }

  async function handleTriggerReview(incidentId: string) {
    try {
      await apiFetch(`/api/v1/incidents/${incidentId}/trigger-review`, { method: "POST" });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to trigger review");
    }
  }

  async function handleLinkControl() {
    if (!selectedControlId) return;
    try {
      await apiFetch(`/api/v1/risks/${id}/controls`, {
        method: "POST",
        body: { control_id: selectedControlId },
      });
      setSelectedControlId("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to link control");
    }
  }

  async function handleUnlinkControl(controlId: string) {
    try {
      await apiFetch(`/api/v1/risks/${id}/controls/${controlId}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to unlink control");
    }
  }

  async function handleCreateAction() {
    if (!newActionTitle.trim()) return;
    try {
      await apiFetch("/api/v1/actions", {
        method: "POST",
        body: { risk_id: id, title: newActionTitle },
      });
      setNewActionTitle("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to create action");
    }
  }

  const linkableControls = allControls.filter((c) => !controls.some((linked) => linked.id === c.id));

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
      <div className="flex items-start justify-between">
        <div>
          <p className="font-mono text-xs text-slate-500">{risk.risk_code}</p>
          <h1 className="text-xl font-semibold text-slate-900">{risk.title}</h1>
          {risk.statement && <p className="mt-1 text-sm text-slate-600">{risk.statement}</p>}
        </div>
        <Link
          href={`/simulations?risk_id=${risk.id}`}
          className="whitespace-nowrap text-sm text-slate-600 underline hover:text-slate-900"
        >
          Run Monte Carlo simulation
        </Link>
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
        <div>
          <p className="text-xs uppercase text-slate-500">Appetite</p>
          <p className={`text-sm ${APPETITE_TONE[risk.appetite_status ?? "not_configured"]}`}>
            {APPETITE_LABELS[risk.appetite_status ?? "not_configured"]}
          </p>
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
        <h2 className="mb-3 text-sm font-semibold text-slate-900">Controls</h2>
        <ul className="mb-3 space-y-1 text-sm">
          {controls.map((c) => (
            <li key={c.id} className="flex items-center justify-between">
              <Link href={`/controls/${c.id}`} className="hover:underline">
                {c.name}
              </Link>
              <button
                onClick={() => handleUnlinkControl(c.id)}
                className="text-xs text-slate-400 hover:text-severity-extreme"
              >
                Unlink
              </button>
            </li>
          ))}
          {controls.length === 0 && <li className="text-slate-500">No controls linked yet.</li>}
        </ul>
        <div className="flex gap-2">
          <select
            value={selectedControlId}
            onChange={(e) => setSelectedControlId(e.target.value)}
            className="flex-1 rounded-md border border-surface-border px-2 py-1.5 text-sm"
          >
            <option value="">Select a control to link…</option>
            {linkableControls.map((c) => (
              <option key={c.id} value={c.id}>
                {c.control_code} — {c.name}
              </option>
            ))}
          </select>
          <Button variant="secondary" onClick={handleLinkControl} disabled={!selectedControlId}>
            Link
          </Button>
        </div>
      </div>

      <div className="rounded-lg border border-surface-border bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">Actions</h2>
        <ul className="mb-3 space-y-1 text-sm">
          {actions.map((a) => (
            <li key={a.id} className="flex items-center justify-between">
              <Link href="/actions" className="hover:underline">
                {a.title}
              </Link>
              <span className="text-slate-500 capitalize">{a.status.replace(/_/g, " ")}</span>
            </li>
          ))}
          {actions.length === 0 && <li className="text-slate-500">No actions yet.</li>}
        </ul>
        <div className="flex gap-2">
          <input
            value={newActionTitle}
            onChange={(e) => setNewActionTitle(e.target.value)}
            placeholder="New action title…"
            className="flex-1 rounded-md border border-surface-border px-2 py-1.5 text-sm"
          />
          <Button variant="secondary" onClick={handleCreateAction} disabled={!newActionTitle.trim()}>
            Add
          </Button>
        </div>
      </div>

      <div className="rounded-lg border border-surface-border bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">Issues</h2>
        <ul className="mb-3 space-y-2 text-sm">
          {issues.map((i) => (
            <li key={i.id} className="border-b border-surface-border pb-2 last:border-0">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-slate-500">{i.issue_code}</span>
                <span className="capitalize text-slate-500">{i.status}</span>
              </div>
              <p className="text-slate-700">{i.description}</p>
            </li>
          ))}
          {issues.length === 0 && <li className="text-slate-500">No issues logged.</li>}
        </ul>
        <div className="flex gap-2">
          <input
            value={newIssueDescription}
            onChange={(e) => setNewIssueDescription(e.target.value)}
            placeholder="Describe an issue found for this risk…"
            className="flex-1 rounded-md border border-surface-border px-2 py-1.5 text-sm"
          />
          <Button variant="secondary" onClick={handleCreateIssue} disabled={!newIssueDescription.trim()}>
            Log issue
          </Button>
        </div>
      </div>

      <div className="rounded-lg border border-surface-border bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">Incidents</h2>
        <ul className="mb-3 space-y-2 text-sm">
          {incidents.map((incident) => (
            <li key={incident.id} className="border-b border-surface-border pb-2 last:border-0">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-slate-500">{incident.incident_code}</span>
                <span className="capitalize text-slate-500">
                  {incident.severity} · {incident.incident_date}
                </span>
              </div>
              <p className="text-slate-700">{incident.description}</p>
              <div className="mt-1 flex items-center justify-between">
                <span className="text-xs text-slate-400">
                  {incident.review_triggered_at
                    ? `Review triggered ${new Date(incident.review_triggered_at).toLocaleDateString()}`
                    : "Review not triggered"}
                </span>
                {canTriggerReview && !incident.review_triggered_at && (
                  <button
                    onClick={() => handleTriggerReview(incident.id)}
                    className="text-xs text-slate-500 underline hover:text-slate-900"
                  >
                    Trigger review
                  </button>
                )}
              </div>
            </li>
          ))}
          {incidents.length === 0 && <li className="text-slate-500">No incidents logged.</li>}
        </ul>
        <div className="flex gap-2">
          <input
            value={newIncidentDescription}
            onChange={(e) => setNewIncidentDescription(e.target.value)}
            placeholder="Describe an incident tied to this risk…"
            className="flex-1 rounded-md border border-surface-border px-2 py-1.5 text-sm"
          />
          <select
            value={newIncidentSeverity}
            onChange={(e) => setNewIncidentSeverity(e.target.value as IncidentSeverity)}
            className="rounded-md border border-surface-border px-2 py-1.5 text-sm"
          >
            <option value="low">Low</option>
            <option value="moderate">Moderate</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
          <Button variant="secondary" onClick={handleCreateIncident} disabled={!newIncidentDescription.trim()}>
            Log incident
          </Button>
        </div>
      </div>

      <RiskAiAnalysisPanel
        riskId={risk.id}
        isOwnRisk={risk.owner_id === session?.user_id}
        onRiskChanged={load}
      />

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

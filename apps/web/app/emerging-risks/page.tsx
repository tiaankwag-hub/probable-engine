"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { RequireAuth } from "@/components/require-auth";
import { Button } from "@/components/ui/button";
import { ApiError, apiFetch } from "@/lib/api";
import type { BackgroundJob, CandidateLifecycleStatus, EmergingRiskCandidate, Risk } from "@/lib/types";

const POLL_INTERVAL_MS = 2000;

const STATUS_LABELS: Record<CandidateLifecycleStatus, string> = {
  candidate: "Candidate",
  under_review: "Under Review",
  accepted: "Accepted",
  linked_to_existing: "Linked to Existing",
  dismissed: "Dismissed",
};

const FILTERS: { value: CandidateLifecycleStatus | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "candidate", label: "Candidate" },
  { value: "under_review", label: "Under Review" },
  { value: "accepted", label: "Accepted" },
  { value: "linked_to_existing", label: "Linked to Existing" },
  { value: "dismissed", label: "Dismissed" },
];

function CandidateCard({
  candidate,
  canReview,
  risks,
  onChanged,
}: {
  candidate: EmergingRiskCandidate;
  canReview: boolean;
  risks: Risk[];
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [linking, setLinking] = useState(false);
  const [selectedRiskId, setSelectedRiskId] = useState("");

  const isActionable = candidate.lifecycle_status === "candidate" || candidate.lifecycle_status === "under_review";

  async function handleTransition(lifecycle_status: CandidateLifecycleStatus) {
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/api/v1/emerging-risks/${candidate.id}`, {
        method: "PATCH",
        body: { lifecycle_status },
      });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to update candidate");
    } finally {
      setBusy(false);
    }
  }

  async function handleLink() {
    if (!selectedRiskId) return;
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/api/v1/emerging-risks/${candidate.id}/link-existing-risk`, {
        method: "POST",
        body: { risk_id: selectedRiskId },
      });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to link to existing risk");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border border-surface-border bg-white p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">{candidate.title}</h3>
          <p className="text-xs text-slate-500">
            {candidate.category_name ?? "Uncategorized"}
            {candidate.model && <> · AI-generated · model: {candidate.model}</>}
          </p>
        </div>
        <span className="whitespace-nowrap text-xs font-medium capitalize text-slate-500">
          {STATUS_LABELS[candidate.lifecycle_status]}
        </span>
      </div>
      <p className="mt-2 text-sm text-slate-700">{candidate.summary}</p>
      <p className="mt-2 text-xs text-slate-500">{candidate.relevance_assessment}</p>

      {candidate.signals.length > 0 && (
        <details className="mt-2 text-xs text-slate-500">
          <summary className="cursor-pointer">
            {candidate.signals.length} source signal{candidate.signals.length > 1 ? "s" : ""}
          </summary>
          <ul className="mt-1 space-y-1 pl-4">
            {candidate.signals.map((s) => (
              <li key={s.id}>
                <a href={s.source_citation} target="_blank" rel="noreferrer" className="hover:underline">
                  {s.source_adapter}
                </a>
                : {s.raw_content}
              </li>
            ))}
          </ul>
        </details>
      )}

      {candidate.created_risk_id && (
        <p className="mt-2 text-xs text-slate-500">
          Created risk:{" "}
          <Link href={`/risks/${candidate.created_risk_id}`} className="hover:underline">
            view risk
          </Link>
        </p>
      )}
      {candidate.matched_risk_id && (
        <p className="mt-2 text-xs text-slate-500">
          Matched existing risk:{" "}
          <Link href={`/risks/${candidate.matched_risk_id}`} className="hover:underline">
            view risk
          </Link>
        </p>
      )}

      {error && <p className="mt-2 text-sm text-severity-extreme">{error}</p>}

      {canReview && isActionable && (
        <div className="mt-3 space-y-2">
          <div className="flex flex-wrap gap-2">
            {candidate.lifecycle_status === "candidate" && (
              <Button variant="ghost" onClick={() => handleTransition("under_review")} disabled={busy}>
                Mark Under Review
              </Button>
            )}
            <Button variant="secondary" onClick={() => handleTransition("accepted")} disabled={busy}>
              Accept as Emerging Risk
            </Button>
            <Button variant="ghost" onClick={() => setLinking((v) => !v)} disabled={busy}>
              Link to Existing Risk
            </Button>
            <Button variant="ghost" onClick={() => handleTransition("dismissed")} disabled={busy}>
              Dismiss
            </Button>
          </div>
          {linking && (
            <div className="flex gap-2">
              <select
                value={selectedRiskId}
                onChange={(e) => setSelectedRiskId(e.target.value)}
                className="flex-1 rounded-md border border-surface-border px-2 py-1.5 text-sm"
              >
                <option value="">Select a risk…</option>
                {risks.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.risk_code} — {r.title}
                  </option>
                ))}
              </select>
              <Button variant="secondary" onClick={handleLink} disabled={!selectedRiskId || busy}>
                Link
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function EmergingRisksView() {
  const { session } = useAuth();
  const canIngest = session?.roles.some((r) => ["risk_manager", "administrator"].includes(r));
  const canReview = session?.roles.some((r) => ["risk_manager", "administrator"].includes(r));

  const [candidates, setCandidates] = useState<EmergingRiskCandidate[]>([]);
  const [risks, setRisks] = useState<Risk[]>([]);
  const [filter, setFilter] = useState<CandidateLifecycleStatus | "all">("all");
  const [error, setError] = useState<string | null>(null);
  const [ingesting, setIngesting] = useState(false);
  const [job, setJob] = useState<BackgroundJob | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const [candidateData, riskData] = await Promise.all([
        apiFetch<EmergingRiskCandidate[]>("/api/v1/emerging-risks"),
        apiFetch<Risk[]>("/api/v1/risks"),
      ]);
      setCandidates(candidateData);
      setRisks(riskData);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to load emerging-risk candidates");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const isActive = job?.status === "pending" || job?.status === "running";
    if (isActive && !pollRef.current) {
      pollRef.current = setInterval(async () => {
        try {
          const updated = await apiFetch<BackgroundJob>(`/api/v1/jobs/${job!.id}`);
          setJob(updated);
          if (updated.status === "succeeded") await load();
        } catch (err) {
          setError(err instanceof ApiError ? String(err.detail) : "Failed to poll ingestion job");
        }
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job]);

  async function handleIngest() {
    setIngesting(true);
    setError(null);
    try {
      const { job_id } = await apiFetch<{ job_id: string }>("/api/v1/emerging-risks/ingest", {
        method: "POST",
      });
      setJob({ id: job_id, job_type: "emerging_signal_ingest", status: "pending", error: null });
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to start signal ingestion");
    } finally {
      setIngesting(false);
    }
  }

  const visible = filter === "all" ? candidates : candidates.filter((c) => c.lifecycle_status === filter);
  const isJobActive = job?.status === "pending" || job?.status === "running";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Emerging Risk Radar</h1>
          <p className="mt-1 text-sm text-slate-500">
            Signals from fixture adapters (standing in for a real news/regulatory feed) are
            classified against this organization&apos;s risk categories and triaged by AI into
            candidates below — never authoritative on their own. Accepting one creates a real
            risk with a placeholder, unrated assessment a Risk Owner must still complete; linking
            one points at a risk that already covers it; dismissing discards it.
          </p>
        </div>
        {canIngest && (
          <Button onClick={handleIngest} disabled={ingesting || isJobActive}>
            {isJobActive ? "Ingesting…" : "Ingest new signals"}
          </Button>
        )}
      </div>

      {job?.status === "failed" && <p className="text-sm text-severity-extreme">{job.error}</p>}
      {error && <p className="text-sm text-severity-extreme">{error}</p>}

      <div className="flex gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={`rounded-md px-3 py-1.5 text-sm ${
              filter === f.value ? "bg-slate-900 text-white" : "border border-surface-border text-slate-600"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="space-y-4">
        {visible.map((c) => (
          <CandidateCard key={c.id} candidate={c} canReview={!!canReview} risks={risks} onChanged={load} />
        ))}
        {visible.length === 0 && (
          <p className="text-sm text-slate-500">
            No candidates{filter !== "all" ? ` in "${STATUS_LABELS[filter as CandidateLifecycleStatus]}"` : ""} yet.
            {canIngest && ' Click "Ingest new signals" to scan the fixture feeds.'}
          </p>
        )}
      </div>
    </div>
  );
}

export default function EmergingRisksPage() {
  return (
    <RequireAuth>
      <EmergingRisksView />
    </RequireAuth>
  );
}

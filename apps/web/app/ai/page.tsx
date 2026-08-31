"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { RequireAuth } from "@/components/require-auth";
import { Button } from "@/components/ui/button";
import { ApiError, apiFetch } from "@/lib/api";
import type { AIRun, AISuggestion } from "@/lib/types";

const POLL_INTERVAL_MS = 2000;

function ExecutiveSummaryPanel() {
  const { session } = useAuth();
  const canRequest = session?.roles.some((r) =>
    ["risk_manager", "executive", "administrator"].includes(r),
  );

  const [run, setRun] = useState<AIRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [requesting, setRequesting] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const isActive = run?.status === "pending" || run?.status === "running";
    if (isActive && !pollRef.current) {
      pollRef.current = setInterval(async () => {
        try {
          const updated = await apiFetch<AIRun>(`/api/v1/ai/runs/${run!.id}`);
          setRun(updated);
        } catch (err) {
          setError(err instanceof ApiError ? String(err.detail) : "Failed to poll AI run");
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
  }, [run]);

  async function handleRequest() {
    setRequesting(true);
    setError(null);
    try {
      const newRun = await apiFetch<AIRun>("/api/v1/ai/executive-summary", { method: "POST" });
      setRun(newRun);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to request executive summary");
    } finally {
      setRequesting(false);
    }
  }

  if (!canRequest) return null;

  return (
    <div className="rounded-lg border border-surface-border bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900">Executive Summary</h2>
        <Button onClick={handleRequest} disabled={requesting || run?.status === "pending" || run?.status === "running"}>
          {requesting ? "Requesting…" : "Generate summary"}
        </Button>
      </div>
      {error && <p className="text-sm text-severity-extreme">{error}</p>}
      {run && (run.status === "pending" || run.status === "running") && (
        <p className="text-sm text-slate-500">Generating…</p>
      )}
      {run?.status === "failed" && <p className="text-sm text-severity-extreme">{run.error}</p>}
      {run?.status === "succeeded" && (
        <div>
          <p className="text-sm text-slate-700">{run.narrative}</p>
          <p className="mt-2 text-xs text-slate-400">
            AI-generated · model: {run.model} · human review is not required for narrative
            summaries, only for suggested risk changes below.
          </p>
        </div>
      )}
    </div>
  );
}

function SuggestionCard({
  suggestion,
  onDecision,
}: {
  suggestion: AISuggestion;
  onDecision: (id: string, action: "approve" | "reject") => void;
}) {
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);

  async function handle(action: "approve" | "reject") {
    setBusy(action);
    await onDecision(suggestion.id, action);
    setBusy(null);
  }

  return (
    <div className="border-b border-surface-border py-3 last:border-0">
      <div className="flex items-center justify-between">
        <Link href={`/risks/${suggestion.risk_id}`} className="text-sm font-medium hover:underline">
          {suggestion.summary}
        </Link>
        <span className="text-xs capitalize text-slate-500">{suggestion.human_review_status}</span>
      </div>
      <p className="mt-1 text-sm text-slate-600">{suggestion.rationale}</p>
      <p className="mt-1 text-xs text-slate-400">
        Proposed: {Object.entries(suggestion.proposed_changes).map(([k, v]) => `${k} → ${v}`).join(", ")}
      </p>
      {suggestion.human_review_status === "pending" && (
        <div className="mt-2 flex gap-2">
          <Button variant="secondary" onClick={() => handle("approve")} disabled={busy !== null}>
            {busy === "approve" ? "Approving…" : "Approve"}
          </Button>
          <Button variant="ghost" onClick={() => handle("reject")} disabled={busy !== null}>
            {busy === "reject" ? "Rejecting…" : "Reject"}
          </Button>
        </div>
      )}
    </div>
  );
}

function SuggestionReviewQueue() {
  const { session } = useAuth();
  const canApprove = session?.roles.some((r) => ["risk_manager", "administrator"].includes(r));

  const [suggestions, setSuggestions] = useState<AISuggestion[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await apiFetch<AISuggestion[]>("/api/v1/ai/suggestions", { query: { status: "pending" } });
      setSuggestions(data);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to load suggestions");
    }
  }, []);

  useEffect(() => {
    if (canApprove) load();
  }, [canApprove, load]);

  async function handleDecision(id: string, action: "approve" | "reject") {
    try {
      await apiFetch(`/api/v1/ai/suggestions/${id}/${action}`, { method: "POST" });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : `Failed to ${action} suggestion`);
    }
  }

  if (!canApprove) return null;

  return (
    <div className="rounded-lg border border-surface-border bg-white p-4">
      <h2 className="mb-3 text-sm font-semibold text-slate-900">
        Pending AI Suggestions <span className="font-normal text-slate-400">({suggestions.length})</span>
      </h2>
      <p className="mb-3 text-xs text-slate-500">
        Every suggestion below came from an AI risk analysis and has not changed anything yet —
        approving applies it through the normal risk-update path (versioned, audited); rejecting
        discards it.
      </p>
      {error && <p className="text-sm text-severity-extreme">{error}</p>}
      {suggestions.map((s) => (
        <SuggestionCard key={s.id} suggestion={s} onDecision={handleDecision} />
      ))}
      {suggestions.length === 0 && <p className="text-sm text-slate-500">No pending suggestions.</p>}
    </div>
  );
}

function AIInsightsView() {
  const { session } = useAuth();
  const hasAnyAccess = session?.roles.some((r) =>
    ["risk_manager", "executive", "administrator"].includes(r),
  );

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">AI Insights</h1>
      <p className="text-sm text-slate-500">
        AI-generated content is always advisory. Narrative summaries need no review; any
        suggested change to a risk's assessment sits pending until a Risk Manager or
        Administrator explicitly approves or rejects it — nothing here changes a risk on its
        own. To request an analysis for a specific risk, open that risk's detail page.
      </p>
      <ExecutiveSummaryPanel />
      <SuggestionReviewQueue />
      {!hasAnyAccess && (
        <p className="text-sm text-slate-500">
          Your role doesn&apos;t have access to executive summaries or suggestion review. Open a
          risk you own to request an AI analysis for it.
        </p>
      )}
    </div>
  );
}

export default function AIInsightsPage() {
  return (
    <RequireAuth>
      <AIInsightsView />
    </RequireAuth>
  );
}

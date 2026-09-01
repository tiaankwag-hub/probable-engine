"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { RequireAuth } from "@/components/require-auth";
import { Button } from "@/components/ui/button";
import { ApiError, apiFetch } from "@/lib/api";
import type { IntakeSubmitResult, RiskIntakeSession } from "@/lib/types";

const FIELD_LABELS: Record<string, string> = {
  title: "Title",
  event: "What could happen",
  impact: "Impact",
  cause: "Likely cause",
  category_guess: "Category (best guess)",
  department_guess: "Department / area",
};

const ALLOWED_ROLES = ["risk_owner", "control_owner", "risk_manager", "executive", "administrator"];

function GuidedIntakeChat() {
  const [session, setSession] = useState<RiskIntakeSession | null>(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [starting, setStarting] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState<IntakeSubmitResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    apiFetch<RiskIntakeSession>("/api/v1/risk-intake/sessions", { method: "POST" })
      .then(setSession)
      .catch((err) => setError(err instanceof ApiError ? String(err.detail) : "Failed to start a session"))
      .finally(() => setStarting(false));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [session?.transcript.length]);

  async function handleSend() {
    if (!session || !input.trim() || sending) return;
    setSending(true);
    setError(null);
    try {
      const updated = await apiFetch<RiskIntakeSession>(
        `/api/v1/risk-intake/sessions/${session.id}/messages`,
        { method: "POST", body: { message: input } },
      );
      setSession(updated);
      setInput("");
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to send your message");
    } finally {
      setSending(false);
    }
  }

  async function handleSubmit() {
    if (!session) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await apiFetch<IntakeSubmitResult>(
        `/api/v1/risk-intake/sessions/${session.id}/submit`,
        { method: "POST" },
      );
      setSubmitted(result);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to submit the draft");
    } finally {
      setSubmitting(false);
    }
  }

  if (starting) {
    return <p className="text-sm text-slate-500">Starting a new conversation…</p>;
  }

  if (submitted) {
    return (
      <div className="rounded-lg border border-surface-border bg-white p-6 text-center shadow-card">
        <h2 className="text-lg font-semibold text-slate-900">Thanks — it&apos;s logged as a draft</h2>
        <p className="mx-auto mt-2 max-w-md text-sm text-slate-600">
          <strong>{submitted.risk_code}</strong> is now in the register as a draft. A Risk Manager
          will review it, complete the assessment, and either open it up or follow up with you.
        </p>
        <div className="mt-4 flex justify-center gap-3">
          <Link href={`/risks/${submitted.risk_id}`}>
            <Button variant="secondary">View the draft</Button>
          </Link>
          <Button onClick={() => window.location.reload()}>Raise another</Button>
        </div>
      </div>
    );
  }

  if (!session) {
    return <p className="text-sm text-severity-extreme">{error ?? "Something went wrong."}</p>;
  }

  const isReady = session.status === "ready_to_submit";
  const draftEntries = Object.entries(session.draft_fields).filter(([, v]) => v);

  return (
    <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
      <div className="flex h-[32rem] flex-col rounded-lg border border-surface-border bg-white shadow-card">
        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {session.transcript.map((turn, idx) => (
            <div key={idx} className={`flex ${turn.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                  turn.role === "user" ? "bg-accent text-white" : "bg-surface-muted text-slate-700"
                }`}
              >
                {turn.content}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
        <div className="border-t border-surface-border p-3">
          {error && <p className="mb-2 text-sm text-severity-extreme">{error}</p>}
          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Type your answer…"
              disabled={sending}
              className="flex-1 rounded-md border border-surface-border px-3 py-2 text-sm"
            />
            <Button onClick={handleSend} disabled={sending || !input.trim()}>
              {sending ? "Sending…" : "Send"}
            </Button>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <div className="rounded-lg border border-surface-border bg-white p-4 shadow-card">
          <h2 className="text-sm font-semibold text-slate-900">Draft so far</h2>
          {draftEntries.length === 0 ? (
            <p className="mt-2 text-sm text-slate-500">Nothing captured yet — keep chatting.</p>
          ) : (
            <dl className="mt-2 space-y-2 text-sm">
              {draftEntries.map(([key, value]) => (
                <div key={key}>
                  <dt className="text-xs uppercase text-slate-400">{FIELD_LABELS[key] ?? key}</dt>
                  <dd className="text-slate-700">{value}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>

        {isReady && (
          <div className="rounded-lg border border-accent/30 bg-accent-soft p-4">
            <p className="text-sm text-slate-700">
              Looks ready — submit it as a draft for a Risk Manager to review, or keep chatting to
              add or correct anything first.
            </p>
            <Button className="mt-3 w-full" onClick={handleSubmit} disabled={submitting}>
              {submitting ? "Submitting…" : "Submit for review"}
            </Button>
          </div>
        )}

        <p className="text-xs text-slate-400">
          This never assigns a likelihood or impact score — a Risk Manager records the real
          assessment after reviewing what you&apos;ve described.
        </p>
      </div>
    </div>
  );
}

const STATUS_LABELS: Record<string, string> = {
  in_progress: "In progress",
  ready_to_submit: "Ready to submit",
  submitted: "Submitted",
  abandoned: "Abandoned",
};

function IntakeReviewInbox() {
  const [sessions, setSessions] = useState<RiskIntakeSession[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<RiskIntakeSession[]>("/api/v1/risk-intake/sessions")
      .then(setSessions)
      .catch((err) => setError(err instanceof ApiError ? String(err.detail) : "Failed to load submissions"));
  }, []);

  const submitted = sessions.filter((s) => s.status === "submitted");

  return (
    <div className="rounded-lg border border-surface-border bg-white p-4 shadow-card">
      <h2 className="mb-1 text-sm font-semibold text-slate-900">
        Guided Intake submissions <span className="font-normal text-slate-400">({sessions.length})</span>
      </h2>
      <p className="mb-3 text-xs text-slate-500">
        Every draft below was created by a colleague through this chat, not by AI acting on its
        own — review it like any other draft risk.
      </p>
      {error && <p className="text-sm text-severity-extreme">{error}</p>}
      <div className="max-h-72 space-y-2 overflow-y-auto">
        {sessions.map((s) => (
          <div key={s.id} className="flex items-center justify-between border-b border-surface-border py-2 text-sm last:border-0">
            <div>
              <p className="text-slate-700">{s.draft_fields.title ?? "(untitled)"}</p>
              <p className="text-xs text-slate-400">
                {s.initiated_by_email} · {STATUS_LABELS[s.status]}
              </p>
            </div>
            {s.resulting_risk_id && (
              <Link href={`/risks/${s.resulting_risk_id}`} className="text-xs text-accent hover:underline">
                View draft risk
              </Link>
            )}
          </div>
        ))}
        {sessions.length === 0 && <p className="text-sm text-slate-500">No submissions yet.</p>}
      </div>
      {submitted.length !== sessions.length && (
        <p className="mt-2 text-xs text-slate-400">
          Only submitted sessions create a risk — in-progress ones are still being drafted.
        </p>
      )}
    </div>
  );
}

function RiskIntakeView() {
  const { session } = useAuth();
  const canSubmit = session?.roles.some((r) => ALLOWED_ROLES.includes(r));
  const canReview = session?.roles.some((r) => ["risk_manager", "administrator"].includes(r));

  if (!canSubmit) {
    return (
      <div className="max-w-4xl space-y-6">
        <h1 className="text-xl font-semibold text-slate-900">Report a Risk</h1>
        <p className="text-sm text-slate-500">
          Your role doesn&apos;t have access to Guided Risk Intake. Ask a Risk Manager to raise it
          on your behalf, or use the full Risk Register form if you have access.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Report a Risk</h1>
        <p className="mt-1 text-sm text-slate-500">
          Not sure how to fill out the full risk form? Just describe your concern in your own
          words — this assistant will ask a few short questions and log it as a draft for a Risk
          Manager to review.
        </p>
      </div>
      <GuidedIntakeChat />
      {canReview && <IntakeReviewInbox />}
    </div>
  );
}

export default function RiskIntakePage() {
  return (
    <RequireAuth>
      <RiskIntakeView />
    </RequireAuth>
  );
}

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { RequireAuth } from "@/components/require-auth";
import { Button } from "@/components/ui/button";
import { ApiError, apiDownload, apiFetch } from "@/lib/api";
import type { ReportRun } from "@/lib/types";

const REPORT_LABELS: Record<string, string> = {
  pdf_executive_summary: "PDF Executive Summary",
  pptx_one_slide: "PowerPoint — 1-Slide Summary",
  pptx_two_slide_elt: "PowerPoint — 2-Slide ELT Board Pack",
};

const STATUS_TONE: Record<string, string> = {
  pending: "text-slate-500",
  running: "text-severity-moderate",
  succeeded: "text-severity-low",
  failed: "text-severity-extreme",
};

const POLL_INTERVAL_MS = 2000;

function ReportsView() {
  const { session } = useAuth();
  const canGenerate =
    session?.roles.includes("risk_manager") ||
    session?.roles.includes("executive") ||
    session?.roles.includes("administrator");

  const [runs, setRuns] = useState<ReportRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [requesting, setRequesting] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadRuns = useCallback(async () => {
    try {
      const data = await apiFetch<ReportRun[]>("/api/v1/reports/runs");
      setRuns(data);
      setError(null);
      setForbidden(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setForbidden(true);
      } else {
        setError(err instanceof ApiError ? String(err.detail) : "Failed to load report runs");
      }
    }
  }, []);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  useEffect(() => {
    const hasActiveRun = runs.some((r) => r.status === "pending" || r.status === "running");
    if (hasActiveRun && !pollRef.current) {
      pollRef.current = setInterval(loadRuns, POLL_INTERVAL_MS);
    } else if (!hasActiveRun && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [runs, loadRuns]);

  async function requestReport(kind: "pdf" | "one_slide" | "two_slide_elt") {
    setRequesting(kind);
    setError(null);
    try {
      if (kind === "pdf") {
        await apiFetch("/api/v1/reports/pdf", { method: "POST", body: {} });
      } else {
        await apiFetch("/api/v1/reports/powerpoint", { method: "POST", body: { template: kind } });
      }
      await loadRuns();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to request report");
    } finally {
      setRequesting(null);
    }
  }

  async function handleDownload(run: ReportRun) {
    setDownloadingId(run.id);
    try {
      const { blob, filename } = await apiDownload(`/api/v1/reports/runs/${run.id}/download`);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to download report");
    } finally {
      setDownloadingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">Reports</h1>

      {canGenerate && (
        <div className="rounded-lg border border-surface-border bg-white p-4 shadow-card">
          <h2 className="mb-3 text-sm font-semibold text-slate-900">Generate a report</h2>
          <p className="mb-3 text-sm text-slate-500">
            Renders the current state of the risk register — KPIs, top risks, category
            exposure, and governance indicators. Generation runs in the background; the run
            below updates automatically once it's ready to download.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => requestReport("pdf")} disabled={requesting !== null}>
              {requesting === "pdf" ? "Requesting…" : "PDF Executive Summary"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => requestReport("one_slide")}
              disabled={requesting !== null}
            >
              {requesting === "one_slide" ? "Requesting…" : "PPTX — 1-Slide Summary"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => requestReport("two_slide_elt")}
              disabled={requesting !== null}
            >
              {requesting === "two_slide_elt" ? "Requesting…" : "PPTX — 2-Slide ELT Board Pack"}
            </Button>
          </div>
        </div>
      )}

      {error && <p className="text-sm text-severity-extreme">{error}</p>}

      {forbidden ? (
        <div className="rounded-lg border border-surface-border bg-white p-4 shadow-card">
          <p className="text-sm text-slate-500">
            Your role doesn't have access to reports. Reports are available to Risk Manager,
            Executive, Administrator, and Auditor (view-only).
          </p>
        </div>
      ) : (
      <div className="rounded-lg border border-surface-border bg-white p-4 shadow-card">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">Report Runs</h2>
        <table className="w-full text-sm">
          <thead className="border-b border-surface-border text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="py-2">Report</th>
              <th className="py-2">Requested</th>
              <th className="py-2">Status</th>
              <th className="py-2"></th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id} className="border-b border-surface-border last:border-0">
                <td className="py-2">{REPORT_LABELS[run.report_type] ?? run.report_type}</td>
                <td className="py-2 text-slate-500">{new Date(run.created_at).toLocaleString()}</td>
                <td className="py-2">
                  <span className={`capitalize ${STATUS_TONE[run.status]}`}>{run.status}</span>
                  {run.status === "failed" && run.error && (
                    <span className="ml-2 text-xs text-slate-400">{run.error}</span>
                  )}
                </td>
                <td className="py-2 text-right">
                  {run.status === "succeeded" && (
                    <button
                      onClick={() => handleDownload(run)}
                      disabled={downloadingId === run.id}
                      className="text-slate-600 underline hover:text-slate-900"
                    >
                      {downloadingId === run.id ? "Downloading…" : "Download"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {runs.length === 0 && (
              <tr>
                <td colSpan={4} className="py-6 text-center text-slate-500">
                  No reports generated yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      )}
    </div>
  );
}

export default function ReportsPage() {
  return (
    <RequireAuth>
      <ReportsView />
    </RequireAuth>
  );
}

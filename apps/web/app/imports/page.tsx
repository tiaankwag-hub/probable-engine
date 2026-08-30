"use client";

import { ChangeEvent, useState } from "react";

import { RequireAuth } from "@/components/require-auth";
import { Button } from "@/components/ui/button";
import { ApiError, apiFetch } from "@/lib/api";
import type {
  BackgroundJob,
  ColumnMappingEntry,
  ColumnsResponse,
  CommitResult,
  ImportJob,
  PreviewResult,
  ValidationResult,
} from "@/lib/types";

type Step = "upload" | "map" | "validate" | "preview" | "commit";

function ImportWizard() {
  const [step, setStep] = useState<Step>("upload");
  const [job, setJob] = useState<ImportJob | null>(null);
  const [mapping, setMapping] = useState<ColumnMappingEntry[]>([]);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [backgroundJob, setBackgroundJob] = useState<BackgroundJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const uploaded = await apiFetch<ImportJob>("/api/v1/imports", {
        method: "POST",
        isForm: true,
        body: formData,
      });
      setJob(uploaded);
      const columns = await apiFetch<ColumnsResponse>(`/api/v1/imports/${uploaded.id}/columns`);
      setMapping(columns.suggested_mapping);
      setStep("map");
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirmMapping() {
    if (!job) return;
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/api/v1/imports/${job.id}/mapping`, {
        method: "PUT",
        body: { mappings: mapping },
      });
      const result = await apiFetch<ValidationResult>(`/api/v1/imports/${job.id}/validate`, {
        method: "POST",
      });
      setValidation(result);
      setStep("validate");
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Validation failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleShowPreview() {
    if (!job) return;
    setBusy(true);
    setError(null);
    try {
      const result = await apiFetch<PreviewResult>(`/api/v1/imports/${job.id}/preview`);
      setPreview(result);
      setStep("preview");
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Preview failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleCommit() {
    if (!job) return;
    setBusy(true);
    setError(null);
    try {
      const result = await apiFetch<CommitResult>(`/api/v1/imports/${job.id}/commit`, {
        method: "POST",
      });
      setStep("commit");
      pollJob(result.background_job_id);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Commit failed");
    } finally {
      setBusy(false);
    }
  }

  function pollJob(jobId: string) {
    const interval = setInterval(async () => {
      try {
        const bg = await apiFetch<BackgroundJob>(`/api/v1/jobs/${jobId}`);
        setBackgroundJob(bg);
        if (bg.status === "succeeded" || bg.status === "failed") {
          clearInterval(interval);
        }
      } catch {
        clearInterval(interval);
      }
    }, 1000);
  }

  const blockingErrors = validation?.issues.filter((i) => i.severity === "error") ?? [];

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">Import Wizard</h1>
      <ol className="flex gap-2 text-xs text-slate-500">
        {(["upload", "map", "validate", "preview", "commit"] as Step[]).map((s, i) => (
          <li
            key={s}
            className={
              s === step
                ? "font-semibold text-slate-900"
                : ["upload", "map", "validate", "preview", "commit"].indexOf(step) > i
                  ? "text-slate-700"
                  : ""
            }
          >
            {i + 1}. {s}
          </li>
        ))}
      </ol>

      {error && <p className="text-sm text-severity-extreme">{error}</p>}

      {step === "upload" && (
        <div className="rounded-lg border border-dashed border-surface-border bg-white p-8 text-center">
          <p className="mb-4 text-sm text-slate-600">
            Upload a Risk Register .xlsx file. Columns are mapped in the next step — nothing is
            committed until you confirm.
          </p>
          <input type="file" accept=".xlsx" onChange={handleUpload} disabled={busy} />
        </div>
      )}

      {step === "map" && job && (
        <div className="space-y-4">
          <p className="text-sm text-slate-600">
            Suggested mapping for <strong>{job.filename}</strong>. Adjust the domain field for any
            column before validating.
          </p>
          <div className="max-h-96 overflow-y-auto rounded-lg border border-surface-border bg-white">
            <table className="w-full text-xs">
              <thead className="bg-surface-muted text-left uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">Source column</th>
                  <th className="px-3 py-2">Domain field</th>
                </tr>
              </thead>
              <tbody>
                {mapping.map((entry, idx) => (
                  <tr key={entry.source_column} className="border-t border-surface-border">
                    <td className="px-3 py-2 font-mono">{entry.source_column}</td>
                    <td className="px-3 py-2">
                      <input
                        value={entry.domain_field ?? ""}
                        onChange={(e) => {
                          const next = [...mapping];
                          next[idx] = { ...entry, domain_field: e.target.value || null };
                          setMapping(next);
                        }}
                        className="w-full rounded border border-surface-border px-2 py-1"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Button onClick={handleConfirmMapping} disabled={busy}>
            {busy ? "Validating…" : "Confirm mapping and validate"}
          </Button>
        </div>
      )}

      {step === "validate" && validation && (
        <div className="space-y-4">
          <div className="rounded-lg border border-surface-border bg-white p-4">
            <p className="text-sm">
              {validation.issue_count} issue(s) found —{" "}
              <strong>{blockingErrors.length} blocking error(s)</strong>.
            </p>
            <ul className="mt-3 max-h-64 space-y-1 overflow-y-auto text-xs">
              {validation.issues.map((issue, idx) => (
                <li
                  key={idx}
                  className={issue.severity === "error" ? "text-severity-extreme" : "text-severity-moderate"}
                >
                  Row {issue.row_number} · {issue.field ?? "—"}: {issue.message}
                </li>
              ))}
              {validation.issues.length === 0 && (
                <li className="text-slate-500">No issues — this file is ready to import.</li>
              )}
            </ul>
          </div>
          <Button onClick={handleShowPreview} disabled={busy || blockingErrors.length > 0}>
            {blockingErrors.length > 0 ? "Fix blocking errors before continuing" : "Preview rows"}
          </Button>
        </div>
      )}

      {step === "preview" && preview && (
        <div className="space-y-4">
          <p className="text-sm text-slate-600">
            Showing {preview.rows.length} of {preview.total_rows} rows.
          </p>
          <div className="max-h-96 overflow-auto rounded-lg border border-surface-border bg-white">
            <table className="w-full text-xs">
              <thead className="bg-surface-muted text-left uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">Row</th>
                  <th className="px-3 py-2">risk_code</th>
                  <th className="px-3 py-2">title</th>
                  <th className="px-3 py-2">issues</th>
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row) => (
                  <tr key={row.row_number} className="border-t border-surface-border">
                    <td className="px-3 py-2">{row.row_number}</td>
                    <td className="px-3 py-2 font-mono">{String(row.mapped.risk_code ?? "")}</td>
                    <td className="px-3 py-2">{String(row.mapped.title ?? "")}</td>
                    <td className="px-3 py-2 text-severity-moderate">{row.issues.length || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Button onClick={handleCommit} disabled={busy}>
            {busy ? "Submitting…" : "Commit import"}
          </Button>
        </div>
      )}

      {step === "commit" && (
        <div className="rounded-lg border border-surface-border bg-white p-4 text-sm">
          {!backgroundJob && <p>Import queued — waiting for the worker to process it…</p>}
          {backgroundJob?.status === "running" && <p>Import running…</p>}
          {backgroundJob?.status === "succeeded" && (
            <p className="text-severity-low">Import committed successfully.</p>
          )}
          {backgroundJob?.status === "failed" && (
            <p className="text-severity-extreme">Import failed: {backgroundJob.error}</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function ImportsPage() {
  return (
    <RequireAuth>
      <ImportWizard />
    </RequireAuth>
  );
}

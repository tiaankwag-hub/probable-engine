"use client";

import { useParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { RequireAuth } from "@/components/require-auth";
import { Button } from "@/components/ui/button";
import { ApiError, apiFetch } from "@/lib/api";
import type { Control, ControlTest, ControlTestResult } from "@/lib/types";

function ControlDetail({ id }: { id: string }) {
  const [control, setControl] = useState<Control | null>(null);
  const [tests, setTests] = useState<ControlTest[]>([]);
  const [showTestForm, setShowTestForm] = useState(false);
  const [tester, setTester] = useState("");
  const [testDate, setTestDate] = useState(new Date().toISOString().slice(0, 10));
  const [result, setResult] = useState<ControlTestResult>("effective");
  const [finding, setFinding] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function load() {
    Promise.all([
      apiFetch<Control>(`/api/v1/controls/${id}`),
      apiFetch<ControlTest[]>(`/api/v1/controls/${id}/tests`),
    ])
      .then(([c, t]) => {
        setControl(c);
        setTests(t);
      })
      .catch((err) => setError(String(err)));
  }

  useEffect(load, [id]);

  async function handleSubmitTest(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await apiFetch(`/api/v1/controls/${id}/tests`, {
        method: "POST",
        body: { tester, test_date: testDate, result, finding: finding || null },
      });
      setShowTestForm(false);
      setFinding("");
      load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to record test");
    } finally {
      setSubmitting(false);
    }
  }

  if (error && !control) return <p className="text-sm text-severity-extreme">{error}</p>;
  if (!control) return <p className="text-sm text-slate-500">Loading…</p>;

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <p className="font-mono text-xs text-slate-500">{control.control_code}</p>
        <h1 className="text-xl font-semibold text-slate-900">{control.name}</h1>
        {control.description && <p className="mt-1 text-sm text-slate-600">{control.description}</p>}
      </div>

      <div className="grid grid-cols-2 gap-4 rounded-lg border border-surface-border bg-white p-4 sm:grid-cols-4">
        <div>
          <p className="text-xs uppercase text-slate-500">Type</p>
          <p className="text-sm capitalize">{control.control_type}</p>
        </div>
        <div>
          <p className="text-xs uppercase text-slate-500">Automation</p>
          <p className="text-sm capitalize">{control.automation}</p>
        </div>
        <div>
          <p className="text-xs uppercase text-slate-500">Design effectiveness</p>
          <p className="text-sm">{control.design_effectiveness ?? "—"}/5</p>
        </div>
        <div>
          <p className="text-xs uppercase text-slate-500">Operating effectiveness</p>
          <p className="text-sm">{control.operating_effectiveness ?? "—"}/5</p>
        </div>
      </div>

      <div className="rounded-lg border border-surface-border bg-white p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-900">Test history</h2>
          {!showTestForm && <Button variant="secondary" onClick={() => setShowTestForm(true)}>Record test</Button>}
        </div>

        {showTestForm && (
          <form onSubmit={handleSubmitTest} className="mb-4 space-y-3 rounded-md border border-surface-border p-3">
            <div className="grid grid-cols-2 gap-3">
              <label className="text-sm text-slate-600">
                Tester
                <input
                  required
                  value={tester}
                  onChange={(e) => setTester(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-surface-border px-2 py-1.5 text-sm"
                />
              </label>
              <label className="text-sm text-slate-600">
                Test date
                <input
                  type="date"
                  required
                  value={testDate}
                  onChange={(e) => setTestDate(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-surface-border px-2 py-1.5 text-sm"
                />
              </label>
            </div>
            <label className="block text-sm text-slate-600">
              Result
              <select
                value={result}
                onChange={(e) => setResult(e.target.value as ControlTestResult)}
                className="mt-1 block w-full rounded-md border border-surface-border px-2 py-1.5 text-sm"
              >
                <option value="effective">Effective</option>
                <option value="partially_effective">Partially Effective</option>
                <option value="ineffective">Ineffective</option>
                <option value="not_tested">Not Tested</option>
              </select>
            </label>
            <label className="block text-sm text-slate-600">
              Finding (optional)
              <textarea
                value={finding}
                onChange={(e) => setFinding(e.target.value)}
                rows={2}
                className="mt-1 block w-full rounded-md border border-surface-border px-2 py-1.5 text-sm"
              />
            </label>
            {error && <p className="text-sm text-severity-extreme">{error}</p>}
            <div className="flex gap-2">
              <Button type="submit" disabled={submitting}>
                {submitting ? "Saving…" : "Save test"}
              </Button>
              <Button type="button" variant="ghost" onClick={() => setShowTestForm(false)}>
                Cancel
              </Button>
            </div>
          </form>
        )}

        <ul className="space-y-2 text-sm">
          {tests.map((test) => (
            <li key={test.id} className="border-b border-surface-border pb-2 last:border-0">
              <span className="font-medium capitalize">{test.result.replace(/_/g, " ")}</span>{" "}
              <span className="text-slate-500">
                by {test.tester} on {test.test_date}
              </span>
              {test.finding && <p className="mt-0.5 text-slate-600">{test.finding}</p>}
            </li>
          ))}
          {tests.length === 0 && <li className="text-slate-500">No tests recorded yet.</li>}
        </ul>
      </div>
    </div>
  );
}

export default function ControlDetailPage() {
  const params = useParams<{ id: string }>();
  return (
    <RequireAuth>
      <ControlDetail id={params.id} />
    </RequireAuth>
  );
}

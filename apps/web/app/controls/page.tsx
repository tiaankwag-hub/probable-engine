"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { RequireAuth } from "@/components/require-auth";
import { Button } from "@/components/ui/button";
import { ApiError, apiFetch } from "@/lib/api";
import type { Control, ControlAutomation, ControlType } from "@/lib/types";

function EffectivenessCell({ value }: { value: number | null }) {
  if (value === null) return <span className="text-slate-400">—</span>;
  const tone = value <= 2 ? "text-severity-extreme" : value === 3 ? "text-severity-moderate" : "text-severity-low";
  return <span className={tone}>{value}/5</span>;
}

function NewControlForm({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [controlType, setControlType] = useState<ControlType>("preventive");
  const [automation, setAutomation] = useState<ControlAutomation>("manual");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await apiFetch("/api/v1/controls", {
        method: "POST",
        body: { name, control_type: controlType, automation, status: "active" },
      });
      setName("");
      setOpen(false);
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to create control");
    } finally {
      setSubmitting(false);
    }
  }

  if (!open) return <Button onClick={() => setOpen(true)}>New control</Button>;

  return (
    <form onSubmit={handleSubmit} className="space-y-3 rounded-lg border border-surface-border bg-white p-4 shadow-card">
      <label className="block text-sm text-slate-600">
        Name
        <input
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="mt-1 block w-full rounded-md border border-surface-border px-3 py-2 text-sm"
        />
      </label>
      <div className="grid grid-cols-2 gap-4">
        <label className="block text-sm text-slate-600">
          Type
          <select
            value={controlType}
            onChange={(e) => setControlType(e.target.value as ControlType)}
            className="mt-1 block w-full rounded-md border border-surface-border px-3 py-2 text-sm"
          >
            <option value="preventive">Preventive</option>
            <option value="detective">Detective</option>
            <option value="corrective">Corrective</option>
          </select>
        </label>
        <label className="block text-sm text-slate-600">
          Automation
          <select
            value={automation}
            onChange={(e) => setAutomation(e.target.value as ControlAutomation)}
            className="mt-1 block w-full rounded-md border border-surface-border px-3 py-2 text-sm"
          >
            <option value="manual">Manual</option>
            <option value="automated">Automated</option>
          </select>
        </label>
      </div>
      {error && <p className="text-sm text-severity-extreme">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" disabled={submitting}>
          {submitting ? "Creating…" : "Create control"}
        </Button>
        <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

function ControlsList() {
  const [controls, setControls] = useState<Control[]>([]);
  const [error, setError] = useState<string | null>(null);

  function load() {
    apiFetch<Control[]>("/api/v1/controls")
      .then(setControls)
      .catch((err) => setError(String(err)));
  }

  useEffect(load, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">Controls</h1>
        <NewControlForm onCreated={load} />
      </div>

      {error && <p className="text-sm text-severity-extreme">{error}</p>}

      <div className="overflow-x-auto rounded-lg border border-surface-border bg-white shadow-card">
        <table className="w-full text-sm">
          <thead className="border-b border-surface-border bg-surface-muted text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-2">Code</th>
              <th className="px-4 py-2">Name</th>
              <th className="px-4 py-2">Type</th>
              <th className="px-4 py-2">Automation</th>
              <th className="px-4 py-2">Design</th>
              <th className="px-4 py-2">Operating</th>
              <th className="px-4 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {controls.map((control) => (
              <tr key={control.id} className="border-b border-surface-border last:border-0">
                <td className="px-4 py-2 font-mono text-xs text-slate-600">
                  <Link href={`/controls/${control.id}`} className="hover:underline">
                    {control.control_code}
                  </Link>
                </td>
                <td className="px-4 py-2">
                  <Link href={`/controls/${control.id}`} className="hover:underline">
                    {control.name}
                  </Link>
                </td>
                <td className="px-4 py-2 capitalize text-slate-500">{control.control_type}</td>
                <td className="px-4 py-2 capitalize text-slate-500">{control.automation}</td>
                <td className="px-4 py-2">
                  <EffectivenessCell value={control.design_effectiveness} />
                </td>
                <td className="px-4 py-2">
                  <EffectivenessCell value={control.operating_effectiveness} />
                </td>
                <td className="px-4 py-2 capitalize text-slate-500">{control.status}</td>
              </tr>
            ))}
            {controls.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-slate-500">
                  No controls yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function ControlsPage() {
  return (
    <RequireAuth>
      <ControlsList />
    </RequireAuth>
  );
}

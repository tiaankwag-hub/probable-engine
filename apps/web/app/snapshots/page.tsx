"use client";

import Link from "next/link";
import { ReactNode, useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { RequireAuth } from "@/components/require-auth";
import { Button } from "@/components/ui/button";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { ApiError, apiFetch } from "@/lib/api";
import type { ChangedRisk, Snapshot, WhatChanged } from "@/lib/types";

function ChangeList({
  title,
  items,
  render,
  emptyLabel,
}: {
  title: string;
  items: ChangedRisk[];
  render?: (item: ChangedRisk) => ReactNode;
  emptyLabel: string;
}) {
  return (
    <div className="rounded-lg border border-surface-border bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold text-slate-900">
        {title} <span className="font-normal text-slate-400">({items.length})</span>
      </h3>
      <ul className="space-y-1 text-sm">
        {items.map((item) => (
          <li key={item.id} className="flex items-center justify-between border-b border-surface-border pb-1 last:border-0">
            <Link href={`/risks/${item.id}`} className="hover:underline">
              {item.title}
            </Link>
            {render && <span className="text-slate-500">{render(item)}</span>}
          </li>
        ))}
        {items.length === 0 && <li className="text-slate-500">{emptyLabel}</li>}
      </ul>
    </div>
  );
}

function SnapshotsView() {
  const { session } = useAuth();
  const canManage =
    session?.roles.includes("risk_manager") || session?.roles.includes("administrator");

  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [label, setLabel] = useState("");
  const [capturing, setCapturing] = useState(false);
  const [selectedId, setSelectedId] = useState("");
  const [whatChanged, setWhatChanged] = useState<WhatChanged | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadSnapshots() {
    try {
      const data = await apiFetch<Snapshot[]>("/api/v1/snapshots");
      setSnapshots(data);
      if (!selectedId && data.length > 0) setSelectedId(data[0].id);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to load snapshots");
    }
  }

  useEffect(() => {
    loadSnapshots();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setWhatChanged(null);
      return;
    }
    apiFetch<WhatChanged>("/api/v1/dashboard/what-changed", { query: { since_snapshot: selectedId } })
      .then(setWhatChanged)
      .catch((err) => setError(err instanceof ApiError ? String(err.detail) : "Failed to load what-changed"));
  }, [selectedId]);

  async function handleCapture() {
    if (!label.trim()) return;
    setCapturing(true);
    setError(null);
    try {
      await apiFetch("/api/v1/snapshots", { method: "POST", body: { label } });
      setLabel("");
      await loadSnapshots();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to capture snapshot");
    } finally {
      setCapturing(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">Snapshots &amp; What Changed</h1>

      <div className="rounded-lg border border-surface-border bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">Captured Snapshots</h2>
        <ul className="mb-3 space-y-1 text-sm">
          {snapshots.map((s) => (
            <li key={s.id} className="flex items-center justify-between border-b border-surface-border py-1 last:border-0">
              <span>
                {s.label} <span className="text-slate-400">— {s.period_end}</span>
              </span>
              <span className="text-slate-500">{s.risk_count} risks</span>
            </li>
          ))}
          {snapshots.length === 0 && <li className="text-slate-500">No snapshots captured yet.</li>}
        </ul>
        {canManage && (
          <div className="flex gap-2">
            <input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Snapshot label, e.g. Q3 close…"
              className="flex-1 rounded-md border border-surface-border px-2 py-1.5 text-sm"
            />
            <Button onClick={handleCapture} disabled={!label.trim() || capturing}>
              {capturing ? "Capturing…" : "Capture snapshot"}
            </Button>
          </div>
        )}
      </div>

      {error && <p className="text-sm text-severity-extreme">{error}</p>}

      {snapshots.length > 0 && (
        <div className="space-y-4">
          <label className="block text-sm text-slate-600">
            Compare current register against
            <select
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
              className="mt-1 block w-full max-w-sm rounded-md border border-surface-border px-2 py-1.5 text-sm"
            >
              {snapshots.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label} ({s.period_end})
                </option>
              ))}
            </select>
          </label>

          {whatChanged && (
            <div className="grid gap-4 lg:grid-cols-2">
              <ChangeList title="New risks" items={whatChanged.new_risks} emptyLabel="No new risks." />
              <ChangeList title="Closed risks" items={whatChanged.closed_risks} emptyLabel="No risks closed." />
              <ChangeList
                title="Escalated"
                items={whatChanged.escalated_risks}
                render={(i) => (
                  <span>
                    {i.from_band} <SeverityBadge band={i.to_band ?? null} />
                  </span>
                )}
                emptyLabel="No risks escalated."
              />
              <ChangeList
                title="Downgraded"
                items={whatChanged.downgraded_risks}
                render={(i) => (
                  <span>
                    {i.from_band} <SeverityBadge band={i.to_band ?? null} />
                  </span>
                )}
                emptyLabel="No risks downgraded."
              />
              <ChangeList title="Owner changes" items={whatChanged.owner_changes} emptyLabel="No owner changes." />
              <ChangeList
                title="Appetite status changes"
                items={whatChanged.appetite_changes}
                render={(i) => `${i.from_status} → ${i.to_status}`}
                emptyLabel="No appetite status changes."
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function SnapshotsPage() {
  return (
    <RequireAuth>
      <SnapshotsView />
    </RequireAuth>
  );
}

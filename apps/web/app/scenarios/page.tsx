"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { RequireAuth } from "@/components/require-auth";
import { Button } from "@/components/ui/button";
import { ApiError, apiFetch } from "@/lib/api";
import type { Scenario } from "@/lib/types";

function ScenariosView() {
  const { session } = useAuth();
  const canManage = session?.roles.includes("risk_manager") || session?.roles.includes("administrator");

  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const data = await apiFetch<Scenario[]>("/api/v1/scenarios");
      setScenarios(data);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to load scenarios");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate() {
    if (!name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await apiFetch("/api/v1/scenarios", {
        method: "POST",
        body: { name, description: description || null },
      });
      setName("");
      setDescription("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to create scenario");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">Scenario Analysis</h1>
      <p className="text-sm text-slate-500">
        A scenario links several risks under one what-if narrative — a regional outage, a major
        vendor failure — so a portfolio Monte Carlo run can quantify their combined, correlated
        exposure rather than each risk in isolation.
      </p>

      {canManage && (
        <div className="rounded-lg border border-surface-border bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-900">New scenario</h2>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Scenario name…"
              className="flex-1 rounded-md border border-surface-border px-2 py-1.5 text-sm"
            />
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Short description (optional)…"
              className="flex-[2] rounded-md border border-surface-border px-2 py-1.5 text-sm"
            />
            <Button onClick={handleCreate} disabled={!name.trim() || creating}>
              {creating ? "Creating…" : "Create"}
            </Button>
          </div>
        </div>
      )}

      {error && <p className="text-sm text-severity-extreme">{error}</p>}

      <div className="rounded-lg border border-surface-border bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">Scenarios</h2>
        <ul className="space-y-2 text-sm">
          {scenarios.map((s) => (
            <li key={s.id} className="flex items-center justify-between border-b border-surface-border pb-2 last:border-0">
              <div>
                <Link href={`/scenarios/${s.id}`} className="font-medium hover:underline">
                  {s.name}
                </Link>
                {s.description && <p className="text-slate-500">{s.description}</p>}
              </div>
              <span className="text-slate-500">{s.linked_risk_ids.length} risk(s) linked</span>
            </li>
          ))}
          {scenarios.length === 0 && <li className="text-slate-500">No scenarios yet.</li>}
        </ul>
      </div>
    </div>
  );
}

export default function ScenariosPage() {
  return (
    <RequireAuth>
      <ScenariosView />
    </RequireAuth>
  );
}

"use client";

import { FormEvent, useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { RequireAuth } from "@/components/require-auth";
import { Button } from "@/components/ui/button";
import { ApiError, apiFetch } from "@/lib/api";
import type { RiskAppetite, RiskCategory } from "@/lib/types";

function AppetiteAdmin() {
  const { session } = useAuth();
  const isAdministrator = session?.roles.includes("administrator") ?? false;

  const [rows, setRows] = useState<RiskAppetite[]>([]);
  const [categories, setCategories] = useState<RiskCategory[]>([]);
  const [categoryId, setCategoryId] = useState("");
  const [businessUnit, setBusinessUnit] = useState("");
  const [appetiteBand, setAppetiteBand] = useState("low");
  const [toleranceBand, setToleranceBand] = useState("moderate");
  const [limitValue, setLimitValue] = useState<number | "">("");
  const [effectiveFrom, setEffectiveFrom] = useState(new Date().toISOString().slice(0, 10));
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function load() {
    apiFetch<RiskAppetite[]>("/api/v1/risk-appetite").then(setRows).catch(() => {});
    apiFetch<RiskCategory[]>("/api/v1/risk-categories").then(setCategories).catch(() => {});
  }

  useEffect(load, []);

  const categoryName = (id: string | null) =>
    categories.find((c) => c.id === id)?.name ?? "All categories";

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await apiFetch("/api/v1/risk-appetite", {
        method: "POST",
        body: {
          category_id: categoryId || null,
          business_unit: businessUnit || null,
          appetite_band: appetiteBand,
          tolerance_band: toleranceBand,
          limit_value: limitValue === "" ? null : limitValue,
          effective_from: effectiveFrom,
          effective_to: null,
        },
      });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to save appetite config");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Risk Appetite</h1>
        <p className="mt-1 text-sm text-slate-500">
          Configured per category (and optionally business unit). A risk's residual band is
          compared against these thresholds to flag it within appetite, approaching tolerance,
          outside appetite, or a material breach — see the Governance Health page.
        </p>
      </div>

      <div className="rounded-lg border border-surface-border bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">Configured thresholds</h2>
        <table className="w-full text-sm">
          <thead className="border-b border-surface-border text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="py-2">Category</th>
              <th className="py-2">Business unit</th>
              <th className="py-2">Appetite</th>
              <th className="py-2">Tolerance</th>
              <th className="py-2">Limit</th>
              <th className="py-2">Effective from</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-b border-surface-border last:border-0">
                <td className="py-2">{categoryName(row.category_id)}</td>
                <td className="py-2 text-slate-500">{row.business_unit ?? "All"}</td>
                <td className="py-2 capitalize">{row.appetite_band}</td>
                <td className="py-2 capitalize">{row.tolerance_band}</td>
                <td className="py-2 text-slate-500">{row.limit_value ?? "—"}</td>
                <td className="py-2 text-slate-500">{row.effective_from}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="py-6 text-center text-slate-500">
                  No appetite configured yet — every risk shows as &quot;not configured&quot;.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {!isAdministrator ? (
        <p className="text-sm text-slate-500">Only Administrators can configure risk appetite.</p>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-surface-border bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-900">Add threshold</h2>
          <div className="grid grid-cols-2 gap-4">
            <label className="text-sm text-slate-600">
              Category
              <select
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
                className="mt-1 block w-full rounded-md border border-surface-border px-2 py-1.5 text-sm"
              >
                <option value="">All categories</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm text-slate-600">
              Business unit (optional)
              <input
                value={businessUnit}
                onChange={(e) => setBusinessUnit(e.target.value)}
                className="mt-1 block w-full rounded-md border border-surface-border px-2 py-1.5 text-sm"
              />
            </label>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <label className="text-sm text-slate-600">
              Appetite band (within)
              <select
                value={appetiteBand}
                onChange={(e) => setAppetiteBand(e.target.value)}
                className="mt-1 block w-full rounded-md border border-surface-border px-2 py-1.5 text-sm"
              >
                <option value="low">Low</option>
                <option value="moderate">Moderate</option>
                <option value="high">High</option>
                <option value="extreme">Extreme</option>
              </select>
            </label>
            <label className="text-sm text-slate-600">
              Tolerance band (approaching)
              <select
                value={toleranceBand}
                onChange={(e) => setToleranceBand(e.target.value)}
                className="mt-1 block w-full rounded-md border border-surface-border px-2 py-1.5 text-sm"
              >
                <option value="low">Low</option>
                <option value="moderate">Moderate</option>
                <option value="high">High</option>
                <option value="extreme">Extreme</option>
              </select>
            </label>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <label className="text-sm text-slate-600">
              Residual-score limit (material breach)
              <input
                type="number"
                step="any"
                value={limitValue}
                onChange={(e) => setLimitValue(e.target.value === "" ? "" : Number(e.target.value))}
                className="mt-1 block w-full rounded-md border border-surface-border px-2 py-1.5 text-sm"
              />
            </label>
            <label className="text-sm text-slate-600">
              Effective from
              <input
                type="date"
                value={effectiveFrom}
                onChange={(e) => setEffectiveFrom(e.target.value)}
                className="mt-1 block w-full rounded-md border border-surface-border px-2 py-1.5 text-sm"
              />
            </label>
          </div>
          {error && <p className="text-sm text-severity-extreme">{error}</p>}
          <Button type="submit" disabled={submitting}>
            {submitting ? "Saving…" : "Save threshold"}
          </Button>
        </form>
      )}
    </div>
  );
}

export default function AppetitePage() {
  return (
    <RequireAuth>
      <AppetiteAdmin />
    </RequireAuth>
  );
}

"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { RequireAuth } from "@/components/require-auth";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { Button } from "@/components/ui/button";
import { ApiError, apiFetch } from "@/lib/api";
import type { RiskAppetite, RiskCategory, ScoringConfig } from "@/lib/types";

const BAND_ORDER = ["low", "moderate", "high", "extreme"] as const;
type Band = (typeof BAND_ORDER)[number];

const BAND_TRACK_CLASS: Record<Band, string> = {
  low: "accent-severity-low",
  moderate: "accent-severity-moderate",
  high: "accent-severity-high",
  extreme: "accent-severity-extreme",
};

/** A 4-stop discrete slider over the ordinal band scale (low..extreme) —
 * replaces a plain <select> so the ordering (and how far apart two bands
 * are) is felt, not just read. Dragging appetite past the current
 * tolerance bumps tolerance up with it, mirroring the backend's
 * `tolerance_band must be at or above appetite_band` rule. */
function BandSlider({
  label,
  value,
  onChange,
  minBand,
}: {
  label: string;
  value: Band;
  onChange: (band: Band) => void;
  minBand?: Band;
}) {
  const index = BAND_ORDER.indexOf(value);
  const minIndex = minBand ? BAND_ORDER.indexOf(minBand) : 0;
  return (
    <div>
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-600">{label}</span>
        <SeverityBadge band={value} />
      </div>
      <input
        type="range"
        min={0}
        max={3}
        step={1}
        value={index}
        onChange={(e) => onChange(BAND_ORDER[Math.max(Number(e.target.value), minIndex)])}
        className={`mt-2 h-1.5 w-full cursor-pointer appearance-none rounded-full bg-surface-border ${BAND_TRACK_CLASS[value]}`}
      />
      <div className="mt-1 flex justify-between text-[11px] capitalize text-slate-400">
        {BAND_ORDER.map((b) => (
          <span key={b} className={b === value ? "font-semibold text-slate-600" : ""}>
            {b}
          </span>
        ))}
      </div>
    </div>
  );
}

function AppetiteAdmin() {
  const { session } = useAuth();
  const isAdministrator = session?.roles.includes("administrator") ?? false;

  const [rows, setRows] = useState<RiskAppetite[]>([]);
  const [categories, setCategories] = useState<RiskCategory[]>([]);
  const [scoringConfigs, setScoringConfigs] = useState<ScoringConfig[]>([]);
  const [categoryId, setCategoryId] = useState("");
  const [businessUnit, setBusinessUnit] = useState("");
  const [appetiteBand, setAppetiteBand] = useState<Band>("low");
  const [toleranceBand, setToleranceBand] = useState<Band>("moderate");
  const [limitEnabled, setLimitEnabled] = useState(false);
  const [limitValue, setLimitValue] = useState(18);
  const [effectiveFrom, setEffectiveFrom] = useState(new Date().toISOString().slice(0, 10));
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function load() {
    apiFetch<RiskAppetite[]>("/api/v1/risk-appetite").then(setRows).catch(() => {});
    apiFetch<RiskCategory[]>("/api/v1/risk-categories").then(setCategories).catch(() => {});
    apiFetch<ScoringConfig[]>("/api/v1/scoring-config").then(setScoringConfigs).catch(() => {});
  }

  useEffect(load, []);

  const categoryName = (id: string | null) =>
    categories.find((c) => c.id === id)?.name ?? "All categories";

  const activeScoringConfig = scoringConfigs.find((c) => c.is_active) ?? scoringConfigs[0] ?? null;
  const scoreCeiling = activeScoringConfig?.band_thresholds.at(-1)?.[0] ?? 25;
  const bandSegments = useMemo(() => {
    if (!activeScoringConfig) return [];
    let previous = 0;
    return activeScoringConfig.band_thresholds.map(([upper, band]) => {
      const segment = { band, from: previous, to: upper, widthPct: ((upper - previous) / scoreCeiling) * 100 };
      previous = upper;
      return segment;
    });
  }, [activeScoringConfig, scoreCeiling]);

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
          limit_value: limitEnabled ? limitValue : null,
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

      <div className="rounded-lg border border-surface-border bg-white p-4 shadow-card">
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
                <td className="py-2">
                  <SeverityBadge band={row.appetite_band} />
                </td>
                <td className="py-2">
                  <SeverityBadge band={row.tolerance_band} />
                </td>
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
        <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-surface-border bg-white p-4 shadow-card">
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
          <div className="grid grid-cols-2 gap-6">
            <BandSlider
              label="Appetite band (within)"
              value={appetiteBand}
              onChange={(band) => {
                setAppetiteBand(band);
                if (BAND_ORDER.indexOf(band) > BAND_ORDER.indexOf(toleranceBand)) setToleranceBand(band);
              }}
            />
            <BandSlider
              label="Tolerance band (approaching)"
              value={toleranceBand}
              onChange={setToleranceBand}
              minBand={appetiteBand}
            />
          </div>
          <p className="text-xs text-slate-400">
            Dragging appetite past the current tolerance brings tolerance up with it — tolerance can
            never sit below appetite, matching how a breach is evaluated.
          </p>

          <div>
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={limitEnabled}
                onChange={(e) => setLimitEnabled(e.target.checked)}
                className="h-4 w-4 rounded border-surface-border accent-accent"
              />
              Set an absolute residual-score limit (material breach ceiling)
            </label>
            {limitEnabled && (
              <div className="mt-3 rounded-md border border-surface-border bg-surface-muted p-3">
                <div className="flex items-center justify-between text-sm text-slate-600">
                  <span>Limit value</span>
                  <span className="font-semibold text-slate-900">{limitValue.toFixed(1)}</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={scoreCeiling}
                  step={0.5}
                  value={Math.min(limitValue, scoreCeiling)}
                  onChange={(e) => setLimitValue(Number(e.target.value))}
                  className="mt-2 h-1.5 w-full cursor-pointer appearance-none rounded-full bg-surface-border accent-accent"
                />
                {bandSegments.length > 0 && (
                  <>
                    <div className="mt-2 flex h-1.5 overflow-hidden rounded-full">
                      {bandSegments.map((seg) => (
                        <div
                          key={seg.band}
                          className={
                            {
                              low: "bg-severity-low",
                              moderate: "bg-severity-moderate",
                              high: "bg-severity-high",
                              extreme: "bg-severity-extreme",
                            }[seg.band] ?? "bg-slate-300"
                          }
                          style={{ width: `${seg.widthPct}%` }}
                          title={`${seg.band} up to ${seg.to}`}
                        />
                      ))}
                    </div>
                    <p className="mt-1 text-[11px] text-slate-400">
                      Reference: the active scoring config's own band boundaries (
                      {bandSegments.map((s) => `${s.band} ≤ ${s.to}`).join(", ")}) on a 0–{scoreCeiling}{" "}
                      residual-score scale — exceeding this limit is always a material breach
                      regardless of band.
                    </p>
                  </>
                )}
              </div>
            )}
          </div>

          <label className="block text-sm text-slate-600">
            Effective from
            <input
              type="date"
              value={effectiveFrom}
              onChange={(e) => setEffectiveFrom(e.target.value)}
              className="mt-1 block w-full max-w-xs rounded-md border border-surface-border px-2 py-1.5 text-sm"
            />
          </label>
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

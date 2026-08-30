"use client";

import type { ImpactScores } from "@/lib/types";

const DIMENSION_LABELS: Record<keyof ImpactScores, string> = {
  financial: "Financial",
  customer_service: "Customer / Service",
  operational_delivery: "Operational Delivery",
  legal_regulatory: "Legal / Regulatory",
  reputation: "Reputation",
  health_safety: "Health & Safety",
};

export function ImpactScoresInput({
  value,
  onChange,
}: {
  value: ImpactScores;
  onChange: (next: ImpactScores) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      {(Object.keys(DIMENSION_LABELS) as (keyof ImpactScores)[]).map((dimension) => (
        <label key={dimension} className="text-sm text-slate-600">
          {DIMENSION_LABELS[dimension]}
          <select
            value={value[dimension]}
            onChange={(e) => onChange({ ...value, [dimension]: Number(e.target.value) })}
            className="mt-1 block w-full rounded-md border border-surface-border px-2 py-1.5 text-sm"
          >
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
      ))}
    </div>
  );
}

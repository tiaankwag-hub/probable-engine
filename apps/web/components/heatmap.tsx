import { cn } from "@/lib/utils";
import type { HeatmapCell } from "@/lib/types";

const BAND_BG: Record<string, string> = {
  low: "bg-severity-low/15",
  moderate: "bg-severity-moderate/20",
  high: "bg-severity-high/25",
  extreme: "bg-severity-extreme/30",
};

const BAND_TEXT: Record<string, string> = {
  low: "text-severity-low",
  moderate: "text-severity-moderate",
  high: "text-severity-high",
  extreme: "text-severity-extreme",
};

/**
 * Classic 5x5 risk matrix: impact increases bottom-to-top, likelihood
 * increases left-to-right. Cell color reflects the dominant residual band
 * among the risks placed there; the count is always shown as text so the
 * information isn't color-only (accessible severity colors — see
 * docs/architecture/01-target-architecture.md).
 */
export function Heatmap({ cells }: { cells: HeatmapCell[] }) {
  const byCoord = new Map(cells.map((c) => [`${c.likelihood}-${c.impact}`, c]));

  return (
    <div className="inline-block">
      <div className="flex">
        <div className="flex flex-col-reverse justify-between pr-2 text-xs text-slate-500">
          {[1, 2, 3, 4, 5].map((impact) => (
            <div key={impact} className="flex h-16 items-center">
              {impact}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-5 gap-1">
          {[5, 4, 3, 2, 1].map((impact) =>
            [1, 2, 3, 4, 5].map((likelihood) => {
              const cell = byCoord.get(`${likelihood}-${impact}`);
              const count = cell?.count ?? 0;
              const band = cell?.dominant_band ?? null;
              return (
                <div
                  key={`${likelihood}-${impact}`}
                  className={cn(
                    "flex h-16 w-16 items-center justify-center rounded border border-surface-border text-sm font-medium",
                    band ? BAND_BG[band] : "bg-surface-muted",
                    band ? BAND_TEXT[band] : "text-slate-400",
                  )}
                  title={`Likelihood ${likelihood}, Impact ${impact}: ${count} risk(s)`}
                >
                  {count || ""}
                </div>
              );
            }),
          )}
        </div>
      </div>
      <div className="mt-1 flex justify-center gap-1 text-xs text-slate-500">
        {[1, 2, 3, 4, 5].map((likelihood) => (
          <div key={likelihood} className="w-16 text-center">
            {likelihood}
          </div>
        ))}
      </div>
      <p className="mt-1 text-center text-xs text-slate-500">Likelihood →  (Impact ↑)</p>
    </div>
  );
}

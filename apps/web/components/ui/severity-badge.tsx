import { cn } from "@/lib/utils";

const BAND_STYLES: Record<string, string> = {
  low: "bg-severity-low/10 text-severity-low border-severity-low/30",
  moderate: "bg-severity-moderate/10 text-severity-moderate border-severity-moderate/30",
  high: "bg-severity-high/10 text-severity-high border-severity-high/30",
  extreme: "bg-severity-extreme/10 text-severity-extreme border-severity-extreme/30",
};

/**
 * Severity is conveyed by label text AND color (never color alone) so the
 * badge remains meaningful for colorblind users and in monochrome print —
 * see docs/architecture/01-target-architecture.md on accessible severity
 * colors.
 */
export function SeverityBadge({ band }: { band: string | null | undefined }) {
  if (!band) {
    return (
      <span className="inline-flex items-center rounded-full border border-surface-border px-2 py-0.5 text-xs text-slate-500">
        Not scored
      </span>
    );
  }
  const style = BAND_STYLES[band] ?? "bg-slate-100 text-slate-700 border-slate-300";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium capitalize",
        style,
      )}
    >
      {band}
    </span>
  );
}

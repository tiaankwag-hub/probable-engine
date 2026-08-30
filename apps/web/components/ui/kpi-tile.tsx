import { cn } from "@/lib/utils";

export function KpiTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | string;
  tone?: "low" | "moderate" | "high" | "extreme" | "neutral";
}) {
  const toneClasses: Record<string, string> = {
    low: "text-severity-low",
    moderate: "text-severity-moderate",
    high: "text-severity-high",
    extreme: "text-severity-extreme",
    neutral: "text-slate-900",
  };
  return (
    <div className="rounded-lg border border-surface-border bg-white p-4">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className={cn("mt-1 text-2xl font-semibold", toneClasses[tone ?? "neutral"])}>
        {value}
      </p>
    </div>
  );
}

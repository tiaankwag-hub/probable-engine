"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { RequireAuth } from "@/components/require-auth";
import { Button } from "@/components/ui/button";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { apiFetchWithHeaders } from "@/lib/api";
import type { Risk } from "@/lib/types";

const PAGE_SIZE = 25;

function RiskRegisterList() {
  const [risks, setRisks] = useState<Risk[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    apiFetchWithHeaders<Risk[]>("/api/v1/risks", {
      query: {
        page,
        page_size: PAGE_SIZE,
        q: query || undefined,
        status: status || undefined,
      },
    })
      .then(({ data, headers }) => {
        if (cancelled) return;
        setRisks(data);
        setTotal(Number(headers.get("X-Total-Count") ?? data.length));
      })
      .catch((err) => !cancelled && setError(String(err)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [page, query, status]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">Risk Register</h1>
        <Link href="/risks/new">
          <Button>New risk</Button>
        </Link>
      </div>

      <div className="flex gap-3">
        <input
          value={query}
          onChange={(e) => {
            setPage(1);
            setQuery(e.target.value);
          }}
          placeholder="Search by title or risk code…"
          className="w-72 rounded-md border border-surface-border px-3 py-2 text-sm"
        />
        <select
          value={status}
          onChange={(e) => {
            setPage(1);
            setStatus(e.target.value);
          }}
          className="rounded-md border border-surface-border px-3 py-2 text-sm"
        >
          <option value="">All statuses</option>
          <option value="draft">Draft</option>
          <option value="open">Open</option>
          <option value="monitoring">Monitoring</option>
          <option value="closed">Closed</option>
        </select>
      </div>

      {error && <p className="text-sm text-severity-extreme">{error}</p>}

      <div className="overflow-x-auto rounded-lg border border-surface-border bg-white">
        <table className="w-full text-sm">
          <thead className="border-b border-surface-border bg-surface-muted text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-2">Risk code</th>
              <th className="px-4 py-2">Title</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">Inherent</th>
              <th className="px-4 py-2">Residual</th>
              <th className="px-4 py-2">Next review</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                  Loading…
                </td>
              </tr>
            )}
            {!loading && risks.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                  No risks found.
                </td>
              </tr>
            )}
            {risks.map((risk) => (
              <tr key={risk.id} className="border-b border-surface-border last:border-0">
                <td className="px-4 py-2 font-mono text-xs text-slate-600">
                  <Link href={`/risks/${risk.id}`} className="hover:underline">
                    {risk.risk_code}
                  </Link>
                </td>
                <td className="px-4 py-2">
                  <Link href={`/risks/${risk.id}`} className="hover:underline">
                    {risk.title}
                  </Link>
                </td>
                <td className="px-4 py-2 capitalize">{risk.status}</td>
                <td className="px-4 py-2">
                  <SeverityBadge band={risk.inherent_band} />
                </td>
                <td className="px-4 py-2">
                  <SeverityBadge band={risk.residual_band} />
                </td>
                <td className="px-4 py-2 text-slate-500">{risk.next_review_date ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm text-slate-500">
        <span>
          {total} risk{total === 1 ? "" : "s"}
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Previous
          </Button>
          <span>
            Page {page} of {totalPages}
          </span>
          <Button
            variant="secondary"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function RisksPage() {
  return (
    <RequireAuth>
      <RiskRegisterList />
    </RequireAuth>
  );
}

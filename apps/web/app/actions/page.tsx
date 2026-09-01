"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { RequireAuth } from "@/components/require-auth";
import { ApiError, apiFetch } from "@/lib/api";
import type { Action, ActionStatus } from "@/lib/types";

const PRIORITY_TONE: Record<string, string> = {
  low: "text-severity-low",
  medium: "text-severity-moderate",
  high: "text-severity-high",
  critical: "text-severity-extreme",
};

function isOverdue(action: Action): boolean {
  if (!action.due_date) return false;
  if (action.status === "completed" || action.status === "cancelled") return false;
  return new Date(action.due_date) < new Date(new Date().toDateString());
}

function ActionsList() {
  const [actions, setActions] = useState<Action[]>([]);
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [statusFilter, setStatusFilter] = useState<ActionStatus | "">("");
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState<string | null>(null);

  function load() {
    apiFetch<Action[]>("/api/v1/actions", {
      query: { overdue: overdueOnly || undefined, status: statusFilter || undefined },
    })
      .then(setActions)
      .catch((err) => setError(String(err)));
  }

  useEffect(load, [overdueOnly, statusFilter]);

  async function markComplete(action: Action) {
    setUpdating(action.id);
    try {
      await apiFetch(`/api/v1/actions/${action.id}`, {
        method: "PATCH",
        body: { status: "completed" },
      });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to update action");
    } finally {
      setUpdating(null);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">Actions</h1>

      <div className="flex items-center gap-4">
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={overdueOnly}
            onChange={(e) => setOverdueOnly(e.target.checked)}
          />
          Overdue only
        </label>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as ActionStatus | "")}
          className="rounded-md border border-surface-border px-3 py-2 text-sm"
        >
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="in_progress">In progress</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      {error && <p className="text-sm text-severity-extreme">{error}</p>}

      <div className="overflow-x-auto rounded-lg border border-surface-border bg-white shadow-card">
        <table className="w-full text-sm">
          <thead className="border-b border-surface-border bg-surface-muted text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-2">Code</th>
              <th className="px-4 py-2">Title</th>
              <th className="px-4 py-2">Priority</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">Completion</th>
              <th className="px-4 py-2">Due date</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {actions.map((action) => (
              <tr key={action.id} className="border-b border-surface-border last:border-0">
                <td className="px-4 py-2 font-mono text-xs text-slate-600">{action.action_code}</td>
                <td className="px-4 py-2">
                  {action.risk_id ? (
                    <Link href={`/risks/${action.risk_id}`} className="hover:underline">
                      {action.title}
                    </Link>
                  ) : (
                    action.title
                  )}
                </td>
                <td className={`px-4 py-2 capitalize ${PRIORITY_TONE[action.priority] ?? ""}`}>
                  {action.priority}
                </td>
                <td className="px-4 py-2 capitalize">
                  {action.status.replace(/_/g, " ")}
                  {isOverdue(action) && (
                    <span className="ml-2 text-xs font-medium text-severity-extreme">overdue</span>
                  )}
                </td>
                <td className="px-4 py-2 text-slate-500">{action.completion_percent}%</td>
                <td className="px-4 py-2 text-slate-500">{action.due_date ?? "—"}</td>
                <td className="px-4 py-2">
                  {action.status !== "completed" && action.status !== "cancelled" && (
                    <button
                      onClick={() => markComplete(action)}
                      disabled={updating === action.id}
                      className="text-xs text-slate-500 hover:text-slate-900 hover:underline"
                    >
                      Mark complete
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {actions.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-slate-500">
                  No actions found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function ActionsPage() {
  return (
    <RequireAuth>
      <ActionsList />
    </RequireAuth>
  );
}

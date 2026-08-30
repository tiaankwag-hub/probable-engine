"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";

const SEED_EMAILS = [
  "viewer@example.com",
  "risk.owner@example.com",
  "control.owner@example.com",
  "risk.manager@example.com",
  "executive@example.com",
  "admin@example.com",
  "auditor@example.com",
];

export default function HomePage() {
  const { session, loading, loginAs } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState(SEED_EMAILS[3]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && session) router.replace("/dashboard");
  }, [loading, session, router]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await loginAs(email);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Sign-in failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto mt-16 max-w-sm rounded-lg border border-surface-border bg-white p-6">
      <h1 className="mb-1 text-lg font-semibold text-slate-900">Sign in</h1>
      <p className="mb-4 text-sm text-slate-500">
        Local mock authentication (ADR 0010) — pick a seeded user. Not a production login.
      </p>
      <form onSubmit={handleSubmit} className="space-y-3">
        <select
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded-md border border-surface-border px-3 py-2 text-sm"
        >
          {SEED_EMAILS.map((seedEmail) => (
            <option key={seedEmail} value={seedEmail}>
              {seedEmail}
            </option>
          ))}
        </select>
        {error && <p className="text-sm text-severity-extreme">{error}</p>}
        <Button type="submit" disabled={submitting} className="w-full">
          {submitting ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </div>
  );
}

"use client";

import { createContext, ReactNode, useContext, useEffect, useState } from "react";

import { apiFetch, clearSession, getSession, setSession, type Session } from "@/lib/api";
import type { MockLoginResponse } from "@/lib/types";

interface AuthContextValue {
  session: Session | null;
  loading: boolean;
  loginAs: (email: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSessionState] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setSessionState(getSession());
    setLoading(false);
  }, []);

  async function loginAs(email: string) {
    const response = await apiFetch<MockLoginResponse>("/api/v1/auth/mock-login", {
      method: "POST",
      body: { email },
    });
    setSession(response);
    setSessionState(response);
  }

  function logout() {
    clearSession();
    setSessionState(null);
  }

  return (
    <AuthContext.Provider value={{ session, loading, loginAs, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

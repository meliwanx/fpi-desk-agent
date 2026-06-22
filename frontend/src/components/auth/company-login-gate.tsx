"use client";

import { type FormEvent, type ReactNode, useEffect, useState } from "react";
import { AlertCircle, Loader2, LockKeyhole } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiErrorMessage } from "@/lib/api";
import { API } from "@/lib/constants";
import { enterpriseApi } from "@/lib/enterprise-api";
import {
  type CompanyLoginResponse,
  type CompanySessionPayload,
  clearCompanySession,
  readCompanySession,
  saveCompanySession,
} from "@/lib/company-auth";

interface CompanySessionResponse {
  user: CompanySessionPayload["user"];
}

export function CompanyLoginGate({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<CompanySessionPayload | null>(null);
  const [checking, setChecking] = useState(true);
  const [email, setEmail] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let mounted = true;
    const existing = readCompanySession();
    if (!existing) {
      setChecking(false);
      return;
    }

    enterpriseApi
      .get<CompanySessionResponse>(API.COMPANY_AUTH.SESSION)
      .then((res) => {
        if (!mounted) return;
        setSession({ ...existing, user: res.user });
      })
      .catch(() => {
        clearCompanySession();
        if (mounted) setSession(null);
      })
      .finally(() => {
        if (mounted) setChecking(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const response = await enterpriseApi.post<CompanyLoginResponse>(
        API.COMPANY_AUTH.LOGIN,
        { email, password },
        { includeCompanySession: false },
      );
      setSession(saveCompanySession(response));
      setPassword("");
    } catch (err) {
      setError(apiErrorMessage(err, "登录失败，请检查账号和密码。"));
    } finally {
      setSubmitting(false);
    }
  };

  if (checking) {
    return (
      <div className="flex h-screen items-center justify-center bg-[var(--surface-chat)] text-[var(--text-secondary)]">
        <Loader2 className="h-5 w-5 animate-spin" />
      </div>
    );
  }

  if (session) return <>{children}</>;

  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--surface-chat)] px-4">
      <section className="w-full max-w-[380px] rounded-lg border border-[var(--border-default)] bg-[var(--surface-primary)] p-5 shadow-[var(--shadow-md)]">
        <div className="mb-5 space-y-4">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/juguang-logo.png"
            width={328}
            height={54}
            alt="聚光科技"
            className="h-auto w-full max-w-[328px]"
          />
          <div className="min-w-0">
            <h1 className="text-base font-semibold text-[var(--text-primary)]">
              聚光办公助理
            </h1>
            <p className="text-xs text-[var(--text-secondary)]">
              公司账号登录
            </p>
          </div>
        </div>

        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-[var(--text-secondary)]" htmlFor="company-account">
              账号
            </label>
            <Input
              id="company-account"
              type="text"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="username"
              placeholder="工号 / 账号"
              className="bg-[var(--surface-secondary)]"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-[var(--text-secondary)]" htmlFor="company-password">
              密码
            </label>
            <Input
              id="company-password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              className="bg-[var(--surface-secondary)]"
            />
          </div>

          {error && (
            <div className="flex items-start gap-2 rounded-md border border-[var(--color-destructive)]/30 bg-[var(--color-destructive)]/5 px-3 py-2 text-xs text-[var(--color-destructive)]">
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <Button
            type="submit"
            className="w-full"
            disabled={!email.trim() || !password || submitting}
          >
            {submitting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <LockKeyhole className="h-4 w-4" />
            )}
            登录
          </Button>
        </form>
      </section>
    </main>
  );
}

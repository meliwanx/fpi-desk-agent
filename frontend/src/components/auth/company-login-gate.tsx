"use client";

import { type FormEvent, type ReactNode, useEffect, useState } from "react";
import {
  AlertCircle,
  Copy,
  Eye,
  EyeOff,
  Loader2,
  LockKeyhole,
  Minus,
  Square,
  UserRound,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiErrorMessage } from "@/lib/api";
import { API, IS_DESKTOP, TITLE_BAR_HEIGHT } from "@/lib/constants";
import { enterpriseApi } from "@/lib/enterprise-api";
import { desktopAPI } from "@/lib/tauri-api";
import { usePlatform } from "@/hooks/use-platform";
import {
  COMPANY_SESSION_CHANGED_EVENT,
  COMPANY_SESSION_STORAGE_KEY,
  type CompanyLoginResponse,
  type CompanySessionPayload,
  clearCompanySession,
  readCompanySession,
  saveCompanySession,
} from "@/lib/company-auth";

interface CompanySessionResponse {
  user: CompanySessionPayload["user"];
}

const REMEMBERED_LOGIN_EMAIL_KEY = "fpi-agent-login-email";
const COMPANY_DEVICE_ID_KEY = "fpi-agent-device-id";

function readRememberedLoginEmail(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(REMEMBERED_LOGIN_EMAIL_KEY) || "";
}

function readCompanyDeviceId(): string {
  if (typeof window === "undefined") return "";
  const existing = localStorage.getItem(COMPANY_DEVICE_ID_KEY);
  if (existing) return existing;
  const generated =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `device-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  localStorage.setItem(COMPANY_DEVICE_ID_KEY, generated);
  return generated;
}

async function readDesktopAppVersion(): Promise<string> {
  if (!IS_DESKTOP) return "";
  try {
    const { getVersion } = await import("@tauri-apps/api/app");
    return await getVersion();
  } catch {
    return "";
  }
}

function LoginWindowControls() {
  const platform = usePlatform();
  const [isMaximized, setIsMaximized] = useState(false);

  useEffect(() => {
    if (!IS_DESKTOP || platform === "macos" || platform === "unknown") return;
    desktopAPI.isMaximized().then(setIsMaximized).catch(() => {});
    return desktopAPI.onMaximizeChange(setIsMaximized);
  }, [platform]);

  if (!IS_DESKTOP) return null;

  if (platform === "macos") {
    return (
      <div
        data-tauri-drag-region
        className="fixed inset-x-0 top-0 z-50 select-none"
        style={{ height: TITLE_BAR_HEIGHT }}
        aria-hidden="true"
      />
    );
  }

  if (platform === "unknown") return null;

  return (
    <div
      data-tauri-drag-region
      className="fixed inset-x-0 top-0 z-50 flex select-none items-center justify-end"
      style={{ height: TITLE_BAR_HEIGHT }}
    >
      <button
        type="button"
        onClick={() => desktopAPI.minimize()}
        className="inline-flex h-full w-[46px] items-center justify-center text-slate-500 transition-colors hover:bg-white/65 hover:text-slate-800"
        aria-label="Minimize"
      >
        <Minus className="h-4 w-4" />
      </button>
      <button
        type="button"
        onClick={() => desktopAPI.maximize()}
        className="inline-flex h-full w-[46px] items-center justify-center text-slate-500 transition-colors hover:bg-white/65 hover:text-slate-800"
        aria-label={isMaximized ? "Restore" : "Maximize"}
      >
        {isMaximized ? <Copy className="h-3.5 w-3.5" /> : <Square className="h-3 w-3" />}
      </button>
      <button
        type="button"
        onClick={() => desktopAPI.close()}
        className="inline-flex h-full w-[46px] items-center justify-center text-slate-500 transition-colors hover:bg-red-600 hover:text-white"
        aria-label="Close"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export function CompanyLoginGate({ children }: { children: ReactNode }) {
  const platform = usePlatform();
  const [session, setSession] = useState<CompanySessionPayload | null>(null);
  const [checking, setChecking] = useState(true);
  const [email, setEmail] = useState(() => readRememberedLoginEmail());
  const [password, setPassword] = useState("");
  const [rememberEmail, setRememberEmail] = useState(() => Boolean(readRememberedLoginEmail()));
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let mounted = true;
    const syncFromStorage = () => {
      if (!mounted) return;
      setSession(readCompanySession());
      setChecking(false);
    };
    const handleStorage = (event: StorageEvent) => {
      if (event.key === COMPANY_SESSION_STORAGE_KEY) syncFromStorage();
    };

    window.addEventListener(COMPANY_SESSION_CHANGED_EVENT, syncFromStorage);
    window.addEventListener("storage", handleStorage);

    const existing = readCompanySession();
    if (!existing) {
      setChecking(false);
      return () => {
        mounted = false;
        window.removeEventListener(COMPANY_SESSION_CHANGED_EVENT, syncFromStorage);
        window.removeEventListener("storage", handleStorage);
      };
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
      window.removeEventListener(COMPANY_SESSION_CHANGED_EVENT, syncFromStorage);
      window.removeEventListener("storage", handleStorage);
    };
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    const account = email.trim();
    try {
      const appVersion = await readDesktopAppVersion();
      const response = await enterpriseApi.post<CompanyLoginResponse>(
        API.COMPANY_AUTH.LOGIN,
        { email: account, password },
        {
          includeCompanySession: false,
          headers: {
            "X-FPI-Device-ID": readCompanyDeviceId(),
            "X-FPI-Device-Name": navigator.platform || navigator.userAgent || "Desktop",
            "X-FPI-Platform": platform === "unknown" ? "" : platform,
            "X-FPI-App-Version": appVersion,
          },
        },
      );
      if (rememberEmail) {
        localStorage.setItem(REMEMBERED_LOGIN_EMAIL_KEY, account);
      } else {
        localStorage.removeItem(REMEMBERED_LOGIN_EMAIL_KEY);
      }
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
      <div className="relative flex h-screen items-center justify-center bg-[#edf4ff] text-slate-500">
        <LoginWindowControls />
        <Loader2 className="h-5 w-5 animate-spin" />
      </div>
    );
  }

  if (session) return <>{children}</>;

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#edf4ff] text-slate-900">
      <LoginWindowControls />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/login-bg.png"
        alt=""
        className="absolute inset-0 h-full w-full object-cover"
        aria-hidden="true"
      />
      <div className="absolute inset-0 bg-[#f3f8ff]/35" aria-hidden="true" />

      <section className="relative z-10 flex min-h-screen items-center justify-center px-6 py-12 sm:px-10 lg:justify-end lg:px-[clamp(56px,8vw,120px)]">
        <div className="w-full max-w-[352px] rounded-lg border border-white/80 bg-white/95 px-8 py-8 shadow-[0_22px_70px_rgba(39,72,120,0.16)] backdrop-blur">
          <div className="mb-6">
            <h1 className="text-[26px] font-semibold leading-tight tracking-normal text-slate-900">
              欢迎登录
            </h1>
            <p className="mt-2 text-sm text-slate-500">
              聚光智能办公助手
            </p>
          </div>

          <form className="space-y-5" onSubmit={handleSubmit}>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700" htmlFor="company-account">
                账号
              </label>
              <div className="relative">
                <UserRound className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <Input
                  id="company-account"
                  type="text"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  autoComplete="username"
                  placeholder="请输入账号"
                  className="h-11 rounded-md border-slate-200 bg-white pl-10 text-slate-900 shadow-none placeholder:text-slate-400 focus-visible:ring-blue-500/20"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700" htmlFor="company-password">
                密码
              </label>
              <div className="relative">
                <LockKeyhole className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <Input
                  id="company-password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                  placeholder="请输入密码"
                  className="h-11 rounded-md border-slate-200 bg-white pl-10 pr-10 text-slate-900 shadow-none placeholder:text-slate-400 focus-visible:ring-blue-500/20"
                />
                <button
                  type="button"
                  className="absolute right-3 top-1/2 inline-flex h-6 w-6 -translate-y-1/2 items-center justify-center text-slate-400 transition-colors hover:text-slate-700"
                  onClick={() => setShowPassword((value) => !value)}
                  aria-label={showPassword ? "隐藏密码" : "显示密码"}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between gap-3">
              <label className="inline-flex cursor-pointer items-center gap-2 text-xs font-medium text-slate-600">
                <input
                  type="checkbox"
                  checked={rememberEmail}
                  onChange={(event) => setRememberEmail(event.target.checked)}
                  className="h-3.5 w-3.5 rounded border-slate-300 accent-blue-600"
                />
                记住账号
              </label>
            </div>

            {error && (
              <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs leading-5 text-red-600">
                <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <Button
              type="submit"
              className="h-11 w-full rounded-md bg-[#2f6df6] text-sm font-semibold text-white shadow-[0_10px_24px_rgba(47,109,246,0.24)] hover:bg-[#255fe6]"
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

          <p className="mt-6 text-center text-[11px] leading-5 text-slate-400">
            聚光科技（杭州）股份有限公司 · 可视化发展部
          </p>
        </div>
      </section>
    </main>
  );
}

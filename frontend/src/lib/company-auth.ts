export const COMPANY_SESSION_STORAGE_KEY = "fpi-company-session";
export const COMPANY_SESSION_CHANGED_EVENT = "fpi-company-session-changed";

export interface CompanyUserInfo {
  id: string;
  email: string;
  display_name: string;
  role: string;
}

export interface CompanyLoginResponse {
  session_id: string;
  token: string;
  expires_at: string;
  user: CompanyUserInfo;
}

export interface CompanySessionPayload {
  sessionId?: string;
  token: string;
  expiresAt: string;
  user: CompanyUserInfo;
}

function canUseStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function emitCompanySessionChanged(session: CompanySessionPayload | null): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent(COMPANY_SESSION_CHANGED_EVENT, { detail: session }),
  );
}

export function readCompanySession(): CompanySessionPayload | null {
  if (!canUseStorage()) return null;
  const raw = window.localStorage.getItem(COMPANY_SESSION_STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as CompanySessionPayload;
    if (!parsed.token || !parsed.user?.email) return null;
    if (parsed.expiresAt && Date.parse(parsed.expiresAt) <= Date.now()) {
      clearCompanySession();
      return null;
    }
    return parsed;
  } catch {
    clearCompanySession();
    return null;
  }
}

export function getCompanySessionToken(): string | null {
  return readCompanySession()?.token ?? null;
}

export function saveCompanySession(response: CompanyLoginResponse): CompanySessionPayload {
  const payload: CompanySessionPayload = {
    sessionId: response.session_id,
    token: response.token,
    expiresAt: response.expires_at,
    user: response.user,
  };
  if (canUseStorage()) {
    window.localStorage.setItem(COMPANY_SESSION_STORAGE_KEY, JSON.stringify(payload));
  }
  emitCompanySessionChanged(payload);
  return payload;
}

export function clearCompanySession(): void {
  if (!canUseStorage()) return;
  window.localStorage.removeItem(COMPANY_SESSION_STORAGE_KEY);
  emitCompanySessionChanged(null);
}

export function isCompanyAuthFailure(status: number, body: unknown): boolean {
  if (status !== 401 && status !== 403) return false;
  const detail =
    typeof body === "object" && body !== null && "detail" in body
      ? String((body as { detail?: unknown }).detail ?? "")
      : typeof body === "string"
        ? body
        : "";
  return detail === "Company login required";
}

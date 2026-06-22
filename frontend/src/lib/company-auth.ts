export const COMPANY_SESSION_STORAGE_KEY = "fpi-company-session";

export interface CompanyUserInfo {
  id: string;
  email: string;
  display_name: string;
  role: string;
}

export interface CompanyLoginResponse {
  token: string;
  expires_at: string;
  user: CompanyUserInfo;
}

export interface CompanySessionPayload {
  token: string;
  expiresAt: string;
  user: CompanyUserInfo;
}

function canUseStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
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
    token: response.token,
    expiresAt: response.expires_at,
    user: response.user,
  };
  if (canUseStorage()) {
    window.localStorage.setItem(COMPANY_SESSION_STORAGE_KEY, JSON.stringify(payload));
  }
  return payload;
}

export function clearCompanySession(): void {
  if (!canUseStorage()) return;
  window.localStorage.removeItem(COMPANY_SESSION_STORAGE_KEY);
}

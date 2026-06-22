"use client";

import { getCompanySessionToken } from "./company-auth";
import i18n from "@/i18n/config";

export const ENTERPRISE_CONTROL_URL = (
  process.env.NEXT_PUBLIC_ENTERPRISE_CONTROL_URL || "http://120.26.208.161:5201"
).replace(/\/+$/, "");

class EnterpriseApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public body: unknown,
  ) {
    super(`Enterprise API ${status}: ${statusText}`);
    this.name = "EnterpriseApiError";
  }
}

type EnterpriseRequestInit = RequestInit & {
  timeoutMs?: number;
  includeCompanySession?: boolean;
};

function resolveEnterpriseUrl(path: string): string {
  return path.startsWith("http") ? path : `${ENTERPRISE_CONTROL_URL}${path}`;
}

async function request<T>(
  path: string,
  options?: EnterpriseRequestInit,
): Promise<T> {
  const {
    timeoutMs = 30_000,
    includeCompanySession = true,
    ...fetchOptions
  } = options ?? {};
  const headers = new Headers(fetchOptions.headers);
  headers.set("Content-Type", headers.get("Content-Type") || "application/json");
  headers.set("Accept-Language", headers.get("Accept-Language") || i18n.language || "zh-CN");

  const companyToken = includeCompanySession ? getCompanySessionToken() : null;
  if (companyToken && !headers.has("X-FPI-Session")) {
    headers.set("X-FPI-Session", companyToken);
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(resolveEnterpriseUrl(path), {
      ...fetchOptions,
      headers,
      signal: controller.signal,
    });
    if (!response.ok) {
      const raw = await response.text();
      let body: unknown;
      try {
        body = JSON.parse(raw);
      } catch {
        body = raw;
      }
      throw new EnterpriseApiError(response.status, response.statusText, body);
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("请求企业服务器超时，请检查网络。");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export const enterpriseApi = {
  get: <T>(path: string, options?: EnterpriseRequestInit) => request<T>(path, options),
  post: <T>(path: string, data?: unknown, options?: EnterpriseRequestInit) =>
    request<T>(path, {
      method: "POST",
      body: data ? JSON.stringify(data) : undefined,
      ...options,
    }),
};

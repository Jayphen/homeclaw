const TOKEN_KEY = "homeclaw_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

/** Wrapper around fetch that injects the Authorization header. */
export async function api(
  url: string,
  init?: RequestInit,
): Promise<Response> {
  const token = getToken();
  const headers = new Headers(init?.headers);
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(url, { ...init, headers });
}

/**
 * Build the src URL for a skill's embedded mini-app. The asset is loaded via a
 * browser navigation (iframe), which can't carry the Authorization header, so
 * the session token is appended as a query param.
 *
 * NOTE: token-in-URL is a known weakness (leaks via logs/history/Referer) and
 * is slated for removal once mini-apps authenticate via a postMessage-delivered
 * scoped capability token — see backlog TASK-25/TASK-26. Keep this the single
 * source of truth so that migration is one edit.
 */
export function skillAppSrc(owner: string, name: string, entry: string): string {
  const token = getToken();
  const normalizedEntry = entry.replace(/^\/?assets\//, "").replace(/^\/+/, "");
  const base = `/api/skills/${owner}/${name}/assets/${normalizedEntry || "index.html"}`;
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}

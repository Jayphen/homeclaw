// Host integration for skill mini-apps rendered via @arrow-js/sandbox.
//
// The mini-app's (untrusted, agent-authored) code runs inside a QuickJS+WASM
// VM. It cannot read localStorage / the session token, cannot fetch, and cannot
// touch the host DOM. It reaches data ONLY through the host bridge below, which
// this (already-authenticated) app fulfils on its behalf. The session token
// therefore never enters the sandbox.
import { api } from "$lib/api";

export interface MiniAppSource {
  source: Record<string, string>;
  title?: string | null;
}

/** Minimal local typing for @arrow-js/sandbox (the package ships raw TS source). */
type SandboxFn = (
  props: {
    source: Record<string, string>;
    shadowDOM?: boolean;
    onError?: (error: unknown) => void;
    debug?: boolean;
  },
  events?: { output?: (payload: unknown) => void },
  hostBridge?: Record<string, Record<string, (...args: unknown[]) => unknown>>,
) => (mount: ParentNode) => void;

/** Fetch the source map for a sandboxed skill mini-app. */
export async function fetchAppSource(owner: string, name: string): Promise<MiniAppSource> {
  const r = await api(`/api/skills/${owner}/${name}/app-source`);
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.detail ?? `Failed to load app source (${r.status})`);
  }
  return r.json();
}

/**
 * Host-implemented capability bridge exposed to the sandbox as the bare module
 * `homeclaw`. The mini-app does e.g. `import { query, schema } from 'homeclaw'`.
 * Both calls hit the skill's existing read-only db endpoints, authenticated as
 * the current viewer (the host injects the session token — the sandbox never
 * sees it).
 */
function hostBridge(owner: string, name: string) {
  const base = `/api/skills/${owner}/${name}`;
  return {
    homeclaw: {
      query: async (sql: unknown, params: unknown) => {
        const r = await api(`${base}/db/query`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sql, params: params ?? null }),
        });
        const body = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(body.detail ?? `query failed (${r.status})`);
        return body.rows;
      },
      schema: async () => {
        const r = await api(`${base}/db/schema`);
        const body = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(body.detail ?? `schema failed (${r.status})`);
        return body.tables;
      },
    },
  };
}

/**
 * Lazy-load @arrow-js/sandbox and mount a skill mini-app into `mount`.
 *
 * The WASM VM + compiler (~1.5MB) are dynamically imported here, so they load
 * only when a user actually opens an app — the main UI bundle is unaffected.
 * Returns a teardown function.
 */
export async function mountMiniApp(
  mount: HTMLElement,
  owner: string,
  name: string,
  opts: {
    source: Record<string, string>;
    onError?: (message: string) => void;
    onOutput?: (payload: unknown) => void;
  },
): Promise<() => void> {
  const { sandbox } = (await import("@arrow-js/sandbox")) as { sandbox: SandboxFn };
  const template = sandbox(
    {
      source: opts.source,
      shadowDOM: true,
      onError: (e) => opts.onError?.(String(e)),
    },
    { output: (p) => opts.onOutput?.(p) },
    hostBridge(owner, name),
  );
  template(mount);
  return () => {
    mount.innerHTML = "";
  };
}

<script lang="ts">
  import { api } from "$lib/api";
  import { fetchAppSource, mountMiniApp } from "$lib/sandbox";

  let { params = {} }: { params?: { owner?: string; name?: string } } = $props();

  interface SkillUiApp {
    entry: string;
    title: string | null;
    kind?: "iframe" | "sandbox";
  }

  interface SkillDetail {
    name: string;
    owner: string;
    ui_app: SkillUiApp | null;
  }

  let detail = $state<SkillDetail | null>(null);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);

  // Sandbox mini-app mount state.
  let mountEl = $state<HTMLElement | undefined>();
  let sandboxError = $state<string | null>(null);

  const isSandbox = $derived(detail?.ui_app?.kind === "sandbox");

  async function fetchDetail(owner: string, name: string) {
    loading = true;
    error = null;
    detail = null;
    try {
      const r = await api(`/api/skills/${owner}/${name}`);
      if (!r.ok) throw new Error(`${r.status}`);
      detail = await r.json();
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    if (params.owner && params.name) {
      fetchDetail(params.owner, params.name);
    }
  });

  // Mount the sandboxed mini-app inline once the detail and mount node exist.
  // Re-runs (and tears down) when the target skill changes or on unmount.
  $effect(() => {
    const d = detail;
    const el = mountEl;
    if (!d || d.ui_app?.kind !== "sandbox" || !el) return;

    let cancelled = false;
    let teardown: (() => void) | null = null;
    sandboxError = null;

    (async () => {
      try {
        const { source } = await fetchAppSource(d.owner, d.name);
        if (cancelled) return;
        teardown = await mountMiniApp(el, d.owner, d.name, {
          source,
          onError: (message) => {
            sandboxError = message;
            reportRenderError(d.owner, d.name, message);
          },
        });
      } catch (e: any) {
        if (!cancelled) sandboxError = e?.message ?? String(e);
      }
    })();

    return () => {
      cancelled = true;
      teardown?.();
    };
  });

  // Report a sandbox error to the skill's render log so the agent can read it
  // via skill_render_status (the host is authenticated; the sandbox is not).
  function reportRenderError(owner: string, name: string, message: string): void {
    void api(`/api/skills/${owner}/${name}/_render_log`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, url: `#/apps/${owner}/${name}` }),
    }).catch(() => {});
  }

  const title = $derived(detail?.ui_app?.title || detail?.name || params.name || "App");
</script>

<div class="app-view">
  <header class="app-bar">
    <div class="app-bar-left">
      <a class="back" href="#/apps" aria-label="Back to apps">←</a>
      <h1 class="app-title">{title}</h1>
      {#if detail}
        <span class="owner-tag">{detail.owner}</span>
      {/if}
    </div>
    {#if detail?.ui_app}
      <div class="app-bar-right">
        <a class="bar-link" href="#/skills/{detail.owner}/{detail.name}">Manage skill</a>
      </div>
    {/if}
  </header>

  {#if loading}
    <div class="state">
      <div class="loading">
        <div class="loading-dot"></div>
        <div class="loading-dot"></div>
        <div class="loading-dot"></div>
      </div>
    </div>
  {:else if error}
    <div class="state">
      <div class="error-card">Couldn't load this app: {error}</div>
    </div>
  {:else if detail && detail.ui_app && isSandbox}
    {#if sandboxError}
      <div class="sandbox-error">⚠ Mini-app error: {sandboxError}</div>
    {/if}
    <div bind:this={mountEl} class="app-frame sandbox-mount"></div>
  {:else if detail && detail.ui_app}
    <div class="state">
      <div class="empty">
        <p>This mini-app uses the legacy embedded format, which is no longer supported.</p>
        <p class="empty-hint">
          Ask homeclaw to rebuild it as a sandbox app, or
          <a href="#/skills/{detail.owner}/{detail.name}">manage the skill</a>.
        </p>
      </div>
    </div>
  {:else}
    <div class="state">
      <div class="empty">
        <p>This skill doesn't have a mini-app.</p>
        <p class="empty-hint"><a href="#/apps">Back to apps</a></p>
      </div>
    </div>
  {/if}
</div>

<style>
  .app-view {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    height: calc(100vh - 5.5rem);
    min-height: 480px;
  }

  .app-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .app-bar-left {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    min-width: 0;
  }

  .back {
    text-decoration: none;
    color: var(--text-muted);
    font-size: 1.2rem;
    line-height: 1;
    padding: 0.25rem 0.5rem;
    border-radius: var(--radius-sm);
    transition: color 0.15s, background 0.15s;
  }

  .back:hover {
    color: var(--text);
    background: var(--surface-low);
  }

  .app-title {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 1.4rem;
    color: var(--text);
    letter-spacing: -0.02em;
    margin: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .owner-tag {
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-muted);
    background: var(--surface-low);
    padding: 0.15rem 0.5rem;
    border-radius: var(--radius-pill);
    flex-shrink: 0;
  }

  .app-bar-right {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-shrink: 0;
  }

  .bar-link {
    font-size: 0.8rem;
    font-weight: 500;
    color: var(--text-muted);
    text-decoration: none;
    padding: 0.35rem 0.6rem;
    border-radius: var(--radius-sm);
    transition: color 0.15s, background 0.15s;
  }

  .bar-link:hover {
    color: var(--text);
    background: var(--surface-low);
  }

  .app-frame {
    flex: 1;
    width: 100%;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    background: var(--surface);
    box-shadow: var(--shadow);
  }

  .sandbox-mount {
    overflow: auto;
    padding: 1rem;
  }

  /* The mini-app's host custom element should fill the mount. */
  .sandbox-mount :global(arrow-sandbox) {
    display: block;
    width: 100%;
  }

  .sandbox-error {
    background: #7f1d1d;
    color: #fff;
    font:
      13px/1.5 ui-monospace,
      SFMono-Regular,
      Menlo,
      monospace;
    padding: 0.6rem 0.9rem;
    border-radius: var(--radius-sm);
    white-space: pre-wrap;
  }

  .state {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .loading {
    display: flex;
    gap: 0.4rem;
  }

  .loading-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--primary-container);
    animation: pulse 1.2s ease-in-out infinite;
  }

  .loading-dot:nth-child(2) {
    animation-delay: 0.2s;
  }

  .loading-dot:nth-child(3) {
    animation-delay: 0.4s;
  }

  @keyframes pulse {
    0%,
    100% {
      opacity: 0.3;
      transform: scale(0.8);
    }
    50% {
      opacity: 1;
      transform: scale(1);
    }
  }

  .error-card {
    background: #fef2f0;
    border-radius: var(--radius-sm);
    padding: 0.75rem 1rem;
    font-size: 0.85rem;
    color: var(--secondary);
  }

  .empty {
    text-align: center;
    color: var(--text-muted);
  }

  .empty-hint {
    font-size: 0.88rem;
  }

  .empty a {
    color: var(--primary);
  }
</style>

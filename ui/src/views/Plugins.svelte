<script lang="ts">
  import { api } from "$lib/api";

  interface InstalledPlugin {
    name: string;
    type: string;
    status: string;
    description: string;
    tools: string[];
    routine_count: number;
    error: string | null;
  }

  interface MarketplacePlugin {
    name: string;
    type: string;
    version: string;
    description: string;
    author: string;
  }

  let plugins: InstalledPlugin[] = $state([]);
  let marketplace: MarketplacePlugin[] = $state([]);
  let marketplaceConfigured: boolean = $state(false);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);

  let expandedTools: Set<string> = $state(new Set());
  let toggling: Set<string> = $state(new Set());
  let actionError: string | null = $state(null);

  function toggleTools(name: string) {
    const next = new Set(expandedTools);
    if (next.has(name)) next.delete(name); else next.add(name);
    expandedTools = next;
  }

  function stripNamespace(toolName: string): string {
    const idx = toolName.indexOf("__");
    return idx >= 0 ? toolName.slice(idx + 2) : toolName;
  }

  async function fetchAll() {
    loading = true; error = null;
    try {
      const [pluginsRes, marketplaceRes] = await Promise.all([
        api("/api/plugins"),
        api("/api/plugins/marketplace/browse"),
      ]);
      if (!pluginsRes.ok) throw new Error(`Plugins: ${pluginsRes.status}`);

      const pluginsData = await pluginsRes.json();
      plugins = pluginsData.plugins;

      if (marketplaceRes.ok) {
        const mpData = await marketplaceRes.json();
        marketplace = mpData.plugins;
        marketplaceConfigured = mpData.configured;
      }
    } catch (e: any) { error = e.message; }
    loading = false;
  }

  async function togglePlugin(plugin: InstalledPlugin) {
    toggling = new Set([...toggling, plugin.name]); actionError = null;
    const action = plugin.status === "active" ? "disable" : "enable";
    try {
      const r = await api(`/api/plugins/${plugin.name}/${action}`, { method: "POST" });
      if (!r.ok) { const b = await r.json().catch(() => ({})); throw new Error(b.detail ?? `${r.status}`); }
      const data = await r.json();
      plugins = plugins.map(p => p.name === plugin.name ? data.plugin : p);
    } catch (e: any) { actionError = `Failed to ${action} "${plugin.name}": ${e.message}`; }
    const next = new Set(toggling); next.delete(plugin.name); toggling = next;
  }

  $effect(() => { fetchAll(); });
</script>

{#if loading}
  <div class="loading">
    <div class="loading-dot"></div><div class="loading-dot"></div><div class="loading-dot"></div>
  </div>
{:else if error}
  <div class="error-card"><p>Couldn't load plugins data</p><small>{error}</small></div>
{:else}
  <header class="page-header">
    <h1>Plugins</h1>
    <p class="subtitle">Manage installed plugins and browse the marketplace</p>
  </header>

  {#if actionError}
    <div class="action-error">{actionError}</div>
  {/if}

  <!-- Installed plugins -->
  <section class="section">
    <div class="section-header">
      <h2>Installed</h2>
      <p class="section-desc">Plugins installed in your workspace. Enable a plugin to expose its tools to the assistant.</p>
    </div>

    {#if plugins.length === 0}
      <div class="empty">
        <p>No plugins installed</p>
        <small>Plugins added via chat or the marketplace will appear here.</small>
      </div>
    {:else}
      <div class="plugin-list">
        {#each plugins as plugin, i}
          <div class="plugin-card">
            <div class="plugin-title-row">
              <div class="plugin-identity">
                <span class="plugin-name">{plugin.name}</span>
                <span class="type-badge" class:python={plugin.type === "python"} class:skill={plugin.type === "skill"} class:mcp={plugin.type === "mcp"}>
                  {plugin.type}
                </span>
                <span class="status-dot" class:active={plugin.status === "active"} class:error={plugin.status === "error"} class:disabled={plugin.status === "disabled"}></span>
              </div>
              {#if plugin.type === "python"}
                <button
                  class="btn toggle-btn"
                  class:active={plugin.status === "active"}
                  disabled={toggling.has(plugin.name)}
                  onclick={() => togglePlugin(plugin)}
                >
                  {#if toggling.has(plugin.name)}
                    …
                  {:else if plugin.status === "active"}
                    Enabled
                  {:else}
                    Disabled
                  {/if}
                </button>
              {/if}
            </div>
            {#if plugin.description}
              <p class="plugin-desc">{plugin.description}</p>
            {/if}
            <div class="plugin-meta">
              {#if plugin.tools.length > 0}
                <button class="meta-toggle" onclick={() => toggleTools(plugin.name)}>
                  {plugin.tools.length} {plugin.tools.length === 1 ? "tool" : "tools"}
                  <span class="toggle-arrow" class:open={expandedTools.has(plugin.name)}>▾</span>
                </button>
              {:else}
                <span class="meta-item">No tools</span>
              {/if}
              {#if plugin.routine_count > 0}
                <span class="meta-item">{plugin.routine_count} {plugin.routine_count === 1 ? "routine" : "routines"}</span>
              {/if}
              {#if plugin.error}
                <span class="meta-error">{plugin.error}</span>
              {/if}
            </div>
            {#if expandedTools.has(plugin.name)}
              <ul class="tool-list">
                {#each plugin.tools as tool}<li class="tool-item">{stripNamespace(tool)}</li>{/each}
              </ul>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </section>

  <!-- Marketplace -->
  {#if marketplaceConfigured}
    <section class="section">
      <div class="section-header">
        <h2>Marketplace</h2>
        <p class="section-desc">Browse and install plugins from the community.</p>
      </div>

      {#if marketplace.length === 0}
        <div class="empty">
          <p>No plugins available</p>
          <small>The marketplace is empty or could not be reached.</small>
        </div>
      {:else}
        <div class="plugin-list">
          {#each marketplace as mp, i}
            <div class="plugin-card">
              <div class="plugin-title-row">
                <div class="plugin-identity">
                  <span class="plugin-name">{mp.name}</span>
                  <span class="type-badge" class:python={mp.type === "python"} class:skill={mp.type === "skill"} class:mcp={mp.type === "mcp"}>
                    {mp.type}
                  </span>
                  <span class="version-badge">v{mp.version}</span>
                </div>
              </div>
              {#if mp.description}
                <p class="plugin-desc">{mp.description}</p>
              {/if}
              {#if mp.author}
                <div class="plugin-meta">
                  <span class="meta-item">by {mp.author}</span>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </section>
  {/if}
{/if}

<style>
  .loading { display: flex; justify-content: center; gap: 0.5rem; padding: 4rem 0; }
  .loading-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--primary); opacity: 0.3; animation: pulse 1s ease-in-out infinite; }
  .loading-dot:nth-child(2) { animation-delay: 0.15s; }
  .loading-dot:nth-child(3) { animation-delay: 0.3s; }
  @keyframes pulse { 0%, 100% { opacity: 0.3; transform: scale(1); } 50% { opacity: 1; transform: scale(1.2); } }

  .error-card { background: #fef2f0; border-radius: var(--radius); padding: 1.5rem; text-align: center; color: var(--secondary); }
  .error-card p { margin: 0 0 0.5rem; font-weight: 500; }
  .error-card small { color: var(--text-muted); }

  .action-error { background: #fef2f0; border-radius: var(--radius); padding: 0.6rem 0.9rem; font-size: 0.83rem; color: var(--secondary); margin-bottom: 1rem; }

  .page-header { margin-bottom: 2rem; }
  .page-header h1 { font-family: var(--font-serif); font-weight: 600; font-size: 2rem; margin: 0; color: var(--text); letter-spacing: -0.02em; }
  .subtitle { font-size: 0.85rem; color: var(--text-muted); margin: 0.25rem 0 0; }

  .section { margin-bottom: 2.5rem; }
  .section-header { margin-bottom: 1rem; }
  .section-header h2 { font-family: var(--font-serif); font-weight: 600; font-size: 1.2rem; margin: 0 0 0.3rem; color: var(--text); letter-spacing: -0.01em; }
  .section-desc { font-size: 0.82rem; color: var(--text-muted); margin: 0; line-height: 1.5; }

  /* Installed plugins */
  .plugin-list { display: flex; flex-direction: column; gap: 0.5rem; }
  .plugin-card { background: var(--surface); border-radius: var(--radius); padding: 0.85rem 1.1rem; transition: background 0.15s; }
  .plugin-card:hover { background: var(--surface-low); box-shadow: inset 0 0 0 1px rgba(198, 200, 184, 0.2); }

  .plugin-title-row { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; flex-wrap: wrap; }
  .plugin-identity { display: flex; align-items: center; gap: 0.5rem; }
  .plugin-name { font-weight: 600; font-size: 0.92rem; color: var(--text); }

  .type-badge { font-size: 0.65rem; font-weight: 600; padding: 0.1rem 0.4rem; border-radius: var(--radius-sm); text-transform: uppercase; letter-spacing: 0.04em; background: var(--surface-low); color: var(--text-muted); }
  .type-badge.python { background: #e8eef4; color: #4a7fb5; }
  .type-badge.skill { background: var(--surface-low); color: var(--sage); }
  .type-badge.mcp { background: #f3eef6; color: #8b6aae; }

  .status-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
  .status-dot.active { background: var(--sage); }
  .status-dot.error { background: var(--secondary); }
  .status-dot.disabled { background: var(--text-muted); }

  .version-badge { font-size: 0.68rem; color: var(--text-muted); font-family: monospace; }

  .plugin-desc { font-size: 0.82rem; color: var(--text-muted); margin: 0.3rem 0 0; line-height: 1.45; }

  .plugin-meta { display: flex; align-items: center; gap: 0.75rem; margin-top: 0.4rem; flex-wrap: wrap; }
  .meta-item { font-size: 0.75rem; color: var(--text-muted); }
  .meta-error { font-size: 0.75rem; color: var(--secondary); }

  .meta-toggle { background: none; border: none; padding: 0; font-family: var(--font-sans); font-size: 0.75rem; color: var(--text-muted); cursor: pointer; display: flex; align-items: center; gap: 0.2rem; transition: color 0.15s; }
  .meta-toggle:hover { color: var(--text); }

  .toggle-arrow { display: inline-block; transition: transform 0.2s ease; font-size: 0.7rem; }
  .toggle-arrow.open { transform: rotate(180deg); }

  .toggle-btn { font-size: 0.72rem; padding: 0.2rem 0.55rem; border-radius: var(--radius-pill); background: var(--surface-low); color: var(--text-muted); border: none; transition: background 0.15s, color 0.15s; }
  .toggle-btn.active { background: var(--surface-low); color: var(--primary); }
  .toggle-btn:not(:disabled):hover { background: var(--surface-low); }

  .tool-list { list-style: none; margin: 0.5rem 0 0; padding: 0.5rem 0.75rem; background: var(--surface-low); border-radius: var(--radius-md); display: flex; flex-direction: column; gap: 0.15rem; }
  .tool-item { font-family: monospace; font-size: 0.78rem; color: var(--text-muted); }

  .btn { border: none; border-radius: var(--radius-pill); font-family: var(--font-sans); font-weight: 500; cursor: pointer; transition: filter 0.15s, opacity 0.15s; white-space: nowrap; }
  .btn:disabled { opacity: 0.45; cursor: default; }

  .empty { text-align: center; padding: 2.5rem 1rem; color: var(--text-muted); background: var(--surface-low); border-radius: var(--radius); }
  .empty p { font-family: var(--font-serif); font-style: italic; font-size: 1.05rem; margin: 0 0 0.4rem; }
  .empty small { font-size: 0.82rem; }
</style>

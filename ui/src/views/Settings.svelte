<script lang="ts">
  interface SettingsData {
    enhanced_memory: boolean;
    memsearch_installed: boolean;
    index_exists: boolean;
    semantic_ready: boolean;
  }

  let settings: SettingsData | null = $state(null);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);
  let saving: boolean = $state(false);

  async function fetchSettings() {
    loading = true;
    error = null;
    try {
      const r = await fetch("/api/settings");
      if (!r.ok) throw new Error(`${r.status}`);
      settings = await r.json();
      loading = false;
    } catch (e: any) {
      error = e.message;
      loading = false;
    }
  }

  async function toggleMemory() {
    if (!settings) return;
    saving = true;
    try {
      const r = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enhanced_memory: !settings.enhanced_memory }),
      });
      if (!r.ok) throw new Error(`${r.status}`);
      settings = await r.json();
    } catch (e: any) {
      error = e.message;
    }
    saving = false;
  }

  $effect(() => {
    fetchSettings();
  });
</script>

<div class="settings-page">
  <header class="settings-header">
    <h1>Settings</h1>
  </header>

  {#if loading}
    <div class="loading">
      <div class="loading-dot"></div>
      <div class="loading-dot"></div>
      <div class="loading-dot"></div>
    </div>
  {:else if error}
    <div class="error-card">
      <p>Couldn't load settings.</p>
      <small>{error}</small>
    </div>
  {:else if settings}
    <section class="card">
      <h2>Semantic memory</h2>
      <p class="description">
        Semantic recall uses vector search to find relevant memories from notes and contacts
        when chatting. It goes beyond exact keyword matching to understand meaning.
      </p>

      <div class="status-row">
        <div class="status-item">
          <span class="status-label">memsearch package</span>
          {#if settings.memsearch_installed}
            <span class="status-badge installed">Installed</span>
          {:else}
            <span class="status-badge not-installed">Not installed</span>
          {/if}
        </div>
        {#if settings.memsearch_installed}
          <div class="status-item">
            <span class="status-label">Embedding index</span>
            {#if settings.index_exists}
              <span class="status-badge installed">Ready</span>
            {:else if settings.enhanced_memory}
              <span class="status-badge indexing">Pending first run</span>
            {:else}
              <span class="status-badge not-installed">Not built</span>
            {/if}
          </div>
        {/if}
        <div class="status-item">
          <span class="status-label">Enhanced memory</span>
          <button
            class="toggle"
            class:active={settings.enhanced_memory}
            onclick={toggleMemory}
            disabled={saving}
          >
            <span class="toggle-knob"></span>
          </button>
        </div>
      </div>

      {#if !settings.memsearch_installed}
        <div class="install-guide">
          <h3>Setup</h3>
          <p>Install the semantic memory extra to enable vector recall:</p>
          <code class="install-cmd">pip install homeclaw[semantic]</code>
          <p class="install-note">
            This installs <strong>memsearch</strong> with ONNX for local embeddings — no external
            API needed. After installing, toggle "Enhanced memory" above.
          </p>
        </div>
      {:else if !settings.enhanced_memory}
        <div class="hint">
          <p>memsearch is installed. Toggle "Enhanced memory" above to activate semantic recall.</p>
        </div>
      {:else if !settings.index_exists}
        <div class="hint first-run-hint">
          <h3>First run</h3>
          <p>
            The embedding model (~30–90 MB) will be downloaded automatically on first use.
            After that, your notes and contacts will be indexed locally. This is a one-time
            setup — subsequent starts are fast.
          </p>
          <p>The index will be built the next time you chat or search memories.</p>
        </div>
      {:else}
        <div class="hint active-hint">
          <p>Semantic recall is active. The Recall search will appear on the Memory page.</p>
        </div>
      {/if}
    </section>
  {/if}
</div>

<style>
  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .settings-page {
    animation: fadeUp 0.35s ease-out;
  }

  .settings-header h1 {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 1.6rem;
    margin: 0 0 1.25rem;
    letter-spacing: -0.02em;
    color: var(--text);
  }

  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.25rem 1.5rem;
  }

  .card h2 {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 1.05rem;
    color: var(--text);
    margin: 0 0 0.5rem;
    letter-spacing: -0.01em;
  }

  .description {
    font-size: 0.88rem;
    color: var(--text-muted);
    line-height: 1.5;
    margin: 0 0 1.25rem;
  }

  /* ---- Status row ---- */
  .status-row {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    margin-bottom: 1.25rem;
  }

  .status-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.6rem 0.75rem;
    background: #fdfcfa;
    border-radius: 8px;
    border: 1px solid var(--border);
  }

  .status-label {
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--text);
  }

  .status-badge {
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    letter-spacing: 0.02em;
  }

  .status-badge.installed {
    background: #e8f5e9;
    color: #2e7d32;
  }

  .status-badge.not-installed {
    background: #f0ebe5;
    color: var(--text-muted);
  }

  .status-badge.indexing {
    background: #fff3e0;
    color: #e65100;
  }

  /* ---- Toggle ---- */
  .toggle {
    position: relative;
    width: 42px;
    height: 24px;
    border: none;
    border-radius: 12px;
    background: #d0c8be;
    cursor: pointer;
    transition: background 0.2s;
    padding: 0;
    flex-shrink: 0;
  }

  .toggle.active {
    background: var(--sage);
  }

  .toggle:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .toggle-knob {
    position: absolute;
    top: 3px;
    left: 3px;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #fff;
    transition: transform 0.2s;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
  }

  .toggle.active .toggle-knob {
    transform: translateX(18px);
  }

  /* ---- Install guide ---- */
  .install-guide {
    padding: 1rem;
    background: #fdfcfa;
    border-radius: 8px;
    border: 1px dashed var(--border);
  }

  .install-guide h3 {
    font-family: var(--font-serif);
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--text);
    margin: 0 0 0.5rem;
  }

  .install-guide p {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin: 0 0 0.5rem;
    line-height: 1.4;
  }

  .install-cmd {
    display: block;
    padding: 0.5rem 0.75rem;
    background: var(--text);
    color: #e8e2da;
    border-radius: 6px;
    font-size: 0.82rem;
    font-family: "SF Mono", "Fira Code", monospace;
    margin: 0.5rem 0;
    user-select: all;
  }

  .install-note {
    font-size: 0.8rem;
    color: var(--text-muted);
    margin: 0.5rem 0 0;
  }

  /* ---- Hints ---- */
  .hint {
    padding: 0.75rem 1rem;
    background: #fdfcfa;
    border-radius: 8px;
    border-left: 3px solid var(--amber);
  }

  .hint p {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin: 0;
    line-height: 1.4;
  }

  .active-hint {
    border-left-color: var(--sage);
  }

  .active-hint p {
    color: var(--sage);
  }

  .first-run-hint {
    border-left-color: var(--amber);
  }

  .first-run-hint h3 {
    font-family: var(--font-serif);
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--amber);
    margin: 0 0 0.4rem;
  }

  .first-run-hint p {
    margin: 0 0 0.4rem;
  }

  .first-run-hint p:last-child {
    margin-bottom: 0;
  }

  /* ---- Loading ---- */
  .loading {
    display: flex;
    justify-content: center;
    gap: 0.5rem;
    padding: 4rem 0;
  }

  .loading-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--terracotta);
    opacity: 0.3;
    animation: pulse 1s ease-in-out infinite;
  }

  .loading-dot:nth-child(2) { animation-delay: 0.15s; }
  .loading-dot:nth-child(3) { animation-delay: 0.3s; }

  @keyframes pulse {
    0%, 100% { opacity: 0.3; transform: scale(1); }
    50% { opacity: 1; transform: scale(1.2); }
  }

  .error-card {
    background: #fef2f0;
    border: 1px solid #f0c4bc;
    border-radius: var(--radius);
    padding: 1.5rem;
    text-align: center;
    color: var(--terracotta);
  }

  .error-card p { margin: 0 0 0.5rem; font-weight: 500; }
  .error-card small { color: var(--text-muted); }
</style>

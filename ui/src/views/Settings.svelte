<script lang="ts">
  import { api, getToken, setToken } from "$lib/api";

  interface SettingsData {
    enhanced_memory: boolean;
    memsearch_installed: boolean;
    index_exists: boolean;
    semantic_ready: boolean;
  }

  interface SetupStatus {
    provider_configured: boolean;
    has_password: boolean;
    model: string;
    anthropic_api_key: string | null;
    openai_api_key: string | null;
    openai_base_url: string | null;
    telegram_configured: boolean;
    telegram_allowed_users: string | null;
    ha_configured: boolean;
  }

  let settings: SettingsData | null = $state(null);
  let setup: SetupStatus | null = $state(null);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);
  let saving: boolean = $state(false);
  let saveSuccess: boolean = $state(false);

  // Editable config fields
  let model: string = $state("");
  let anthropicKey: string = $state("");
  let openaiKey: string = $state("");
  let openaiBaseUrl: string = $state("");
  let telegramToken: string = $state("");
  let telegramAllowedUsers: string = $state("");
  let newPassword: string = $state("");
  let newPasswordConfirm: string = $state("");

  async function fetchAll() {
    loading = true;
    error = null;
    try {
      const [settingsRes, setupRes] = await Promise.all([
        api("/api/settings"),
        api("/api/setup/status"),
      ]);
      if (!settingsRes.ok) throw new Error(`Settings: ${settingsRes.status}`);
      if (!setupRes.ok) throw new Error(`Setup: ${setupRes.status}`);
      settings = await settingsRes.json();
      setup = await setupRes.json();
      model = setup!.model;
      openaiBaseUrl = setup!.openai_base_url || "";
      telegramAllowedUsers = setup!.telegram_allowed_users || "";
    } catch (e: any) {
      error = e.message;
    }
    loading = false;
  }

  async function toggleMemory() {
    if (!settings) return;
    saving = true;
    try {
      const r = await api("/api/settings", {
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

  async function saveConfig() {
    error = null;
    saveSuccess = false;

    if (newPassword && newPassword !== newPasswordConfirm) {
      error = "Passwords don't match.";
      return;
    }

    saving = true;
    const body: Record<string, string | null> = {};

    if (model !== setup?.model) body.model = model;
    if (anthropicKey) body.anthropic_api_key = anthropicKey;
    if (openaiKey) body.openai_api_key = openaiKey;
    if (openaiBaseUrl !== (setup?.openai_base_url || "")) body.openai_base_url = openaiBaseUrl || null;
    if (telegramToken) body.telegram_token = telegramToken;
    if (telegramAllowedUsers !== (setup?.telegram_allowed_users || "")) {
      body.telegram_allowed_users = telegramAllowedUsers || null;
    }
    if (newPassword) body.web_password = newPassword;

    if (Object.keys(body).length === 0) {
      saving = false;
      return;
    }

    try {
      const r = await api("/api/setup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const data = await r.json().catch(() => null);
        throw new Error(data?.detail || `Error ${r.status}`);
      }
      setup = await r.json();
      model = setup!.model;
      openaiBaseUrl = setup!.openai_base_url || "";
      telegramAllowedUsers = setup!.telegram_allowed_users || "";

      // Clear secret inputs after save
      anthropicKey = "";
      openaiKey = "";
      telegramToken = "";

      if (newPassword) {
        setToken(newPassword);
        newPassword = "";
        newPasswordConfirm = "";
      }

      saveSuccess = true;
      setTimeout(() => { saveSuccess = false; }, 3000);
    } catch (e: any) {
      error = e.message;
    }
    saving = false;
  }

  $effect(() => {
    fetchAll();
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
      <p>Error</p>
      <small>{error}</small>
      <button class="dismiss" onclick={() => { error = null; }}>Dismiss</button>
    </div>
  {/if}

  {#if !loading && setup}
    <!-- Configuration -->
    <section class="card">
      <h2>LLM provider</h2>

      <div class="field">
        <label for="model">Model</label>
        <input id="model" type="text" bind:value={model} />
      </div>

      <div class="field">
        <label for="anthropic-key">Anthropic API key</label>
        <input id="anthropic-key" type="password" bind:value={anthropicKey}
          placeholder={setup.anthropic_api_key ? `Current: ${setup.anthropic_api_key}` : "Not set"} />
      </div>

      <div class="field">
        <label for="openai-key">OpenAI / OpenRouter API key</label>
        <input id="openai-key" type="password" bind:value={openaiKey}
          placeholder={setup.openai_api_key ? `Current: ${setup.openai_api_key}` : "Not set"} />
      </div>

      <div class="field">
        <label for="base-url">Base URL</label>
        <input id="base-url" type="url" bind:value={openaiBaseUrl} placeholder="https://openrouter.ai/api/v1" />
        <small class="field-hint">For OpenRouter, Ollama, or any OpenAI-compatible API.</small>
      </div>
    </section>

    <section class="card">
      <h2>Telegram</h2>
      <div class="field">
        <label for="tg-token">Bot token</label>
        <input id="tg-token" type="password" bind:value={telegramToken}
          placeholder={setup.telegram_configured ? "Configured (enter new to change)" : "Not set"} />
      </div>
      <div class="field">
        <label for="tg-users">Allowed user IDs</label>
        <input id="tg-users" type="text" bind:value={telegramAllowedUsers} placeholder="12345678, 87654321" />
        <small class="field-hint">Comma-separated. Leave blank for unrestricted.</small>
      </div>
    </section>

    <section class="card">
      <h2>Change password</h2>
      <div class="field">
        <label for="new-pw">New password</label>
        <input id="new-pw" type="password" bind:value={newPassword} placeholder="Leave blank to keep current" />
      </div>
      <div class="field">
        <label for="new-pw-confirm">Confirm new password</label>
        <input id="new-pw-confirm" type="password" bind:value={newPasswordConfirm} placeholder="Confirm" />
      </div>
    </section>

    <div class="save-row">
      <button class="btn primary" onclick={saveConfig} disabled={saving}>
        {saving ? "Saving..." : "Save changes"}
      </button>
      {#if saveSuccess}
        <span class="save-ok">Saved</span>
      {/if}
    </div>
  {/if}

  {#if !loading && settings}
    <!-- Semantic memory (existing section) -->
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
            aria-label="Toggle enhanced memory"
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
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
  }

  .settings-header h1 {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 1.6rem;
    margin: 0;
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
    margin: 0 0 0.75rem;
    letter-spacing: -0.01em;
  }

  .description {
    font-size: 0.88rem;
    color: var(--text-muted);
    line-height: 1.5;
    margin: 0 0 1.25rem;
  }

  /* ---- Fields ---- */
  .field {
    margin-bottom: 0.75rem;
  }

  .field label {
    display: block;
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 0.3rem;
  }

  .field input {
    width: 100%;
    padding: 0.55rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: 8px;
    font-size: 0.85rem;
    font-family: var(--font-sans);
    background: #fdfcfa;
    color: var(--text);
    transition: border-color 0.15s;
  }

  .field input:focus {
    outline: none;
    border-color: var(--terracotta);
  }

  .field input::placeholder {
    color: var(--text-muted);
    opacity: 0.6;
  }

  .field-hint {
    display: block;
    font-size: 0.78rem;
    color: var(--text-muted);
    margin-top: 0.25rem;
  }

  /* ---- Save row ---- */
  .save-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .btn.primary {
    padding: 0.55rem 1.25rem;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    font-family: var(--font-sans);
    cursor: pointer;
    border: none;
    background: var(--terracotta);
    color: #fff;
    transition: filter 0.15s;
  }

  .btn.primary:hover { filter: brightness(1.08); }
  .btn.primary:disabled { opacity: 0.5; cursor: default; }

  .save-ok {
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--sage);
    animation: fadeUp 0.2s ease-out;
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

  .status-badge.installed { background: #e8f5e9; color: #2e7d32; }
  .status-badge.not-installed { background: #f0ebe5; color: var(--text-muted); }
  .status-badge.indexing { background: #fff3e0; color: #e65100; }

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

  .toggle.active { background: var(--sage); }
  .toggle:disabled { opacity: 0.5; cursor: default; }

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

  .toggle.active .toggle-knob { transform: translateX(18px); }

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

  .active-hint { border-left-color: var(--sage); }
  .active-hint p { color: var(--sage); }
  .first-run-hint { border-left-color: var(--amber); }

  .first-run-hint h3 {
    font-family: var(--font-serif);
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--amber);
    margin: 0 0 0.4rem;
  }

  .first-run-hint p { margin: 0 0 0.4rem; }
  .first-run-hint p:last-child { margin-bottom: 0; }

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
    padding: 1rem 1.25rem;
    color: var(--terracotta);
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .error-card p { margin: 0; font-weight: 500; font-size: 0.85rem; }
  .error-card small { color: var(--text-muted); font-size: 0.8rem; }

  .dismiss {
    margin-left: auto;
    padding: 0.3rem 0.6rem;
    border: 1px solid #f0c4bc;
    border-radius: 6px;
    background: transparent;
    color: var(--terracotta);
    font-size: 0.78rem;
    font-weight: 500;
    cursor: pointer;
  }
</style>

<script lang="ts">
  import { api, getToken, setToken } from "$lib/api";

  interface SetupStatus {
    provider_configured: boolean;
    provider: string | null;
    has_password: boolean;
    model: string;
    anthropic_api_key: string | null;
    openai_api_key: string | null;
    openai_base_url: string | null;
    telegram_configured: boolean;
    telegram_allowed_users: string | null;
    jina_api_key: string | null;
    ha_configured: boolean;
    conversation_model: string;
    routine_model: string;
  }

  let setup: SetupStatus | null = $state(null);
  let pageState: "loading" | "ready" | "error" = $state("loading");
  let error: string | null = $state(null);

  // Save state machine: idle → saving → success (auto-clears) or error
  let saveState: "idle" | "saving" | "success" | "error" = $state("idle");
  let saveTimeout: ReturnType<typeof setTimeout> | null = $state(null);

  // Data operation state machine: idle → exporting/importing → result/error
  let dataState: "idle" | "exporting" | "importing" = $state("idle");
  let dataResult: string | null = $state(null);
  let dataError: string | null = $state(null);

  // Editable config fields
  let selectedProvider: "anthropic" | "openai" = $state("anthropic");
  let conversationModel: string = $state("");
  let routineModel: string = $state("");
  let anthropicKey: string = $state("");
  let openaiKey: string = $state("");
  let openaiBaseUrl: string = $state("");
  let jinaKey: string = $state("");
  let telegramToken: string = $state("");
  let telegramAllowedUsers: string = $state("");
  let newPassword: string = $state("");
  let newPasswordConfirm: string = $state("");

  async function exportData() {
    if (dataState !== "idle") return;
    dataState = "exporting";
    dataResult = null;
    dataError = null;
    try {
      const r = await api("/api/data/export");
      if (!r.ok) throw new Error(`${r.status}`);
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const disposition = r.headers.get("Content-Disposition");
      const match = disposition?.match(/filename="(.+)"/);
      a.download = match?.[1] ?? "homeclaw-export.zip";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      dataError = e.message;
    }
    dataState = "idle";
  }

  async function importData(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    if (dataState !== "idle") return;
    dataState = "importing";
    dataResult = null;
    dataError = null;
    try {
      const formData = new FormData();
      formData.append("file", file);
      const r = await api("/api/data/import", { method: "POST", body: formData });
      if (!r.ok) {
        const data = await r.json().catch(() => null);
        throw new Error(data?.detail || `Error ${r.status}`);
      }
      const data = await r.json();
      dataResult = `Imported ${data.files_written} files (${data.members_imported?.length ?? 0} members).`;
    } catch (e: any) {
      dataError = e.message;
    }
    dataState = "idle";
    input.value = "";
  }

  async function fetchAll() {
    pageState = "loading";
    error = null;
    try {
      const setupRes = await api("/api/setup/status");
      if (!setupRes.ok) throw new Error(`${setupRes.status}`);
      setup = await setupRes.json();
      selectedProvider = (setup!.provider === "openai" ? "openai" : setup!.provider === "anthropic" ? "anthropic" : setup!.anthropic_api_key ? "anthropic" : "openai") as "anthropic" | "openai";
      conversationModel = setup!.conversation_model;
      routineModel = setup!.routine_model;
      openaiBaseUrl = setup!.openai_base_url || "";
      telegramAllowedUsers = setup!.telegram_allowed_users || "";
      pageState = "ready";
    } catch (e: any) {
      error = e.message;
      pageState = "error";
    }
  }

  async function saveConfig() {
    if (saveState === "saving") return;
    error = null;
    if (saveTimeout) { clearTimeout(saveTimeout); saveTimeout = null; }

    if (newPassword && newPassword !== newPasswordConfirm) {
      error = "Passwords don't match.";
      return;
    }

    saveState = "saving";
    const body: Record<string, string | null> = {};

    if (selectedProvider !== setup?.provider) body.provider = selectedProvider;
    if (conversationModel !== setup?.conversation_model) body.conversation_model = conversationModel;
    if (routineModel !== setup?.routine_model) body.routine_model = routineModel;
    if (anthropicKey) body.anthropic_api_key = anthropicKey;
    if (openaiKey) body.openai_api_key = openaiKey;
    if (jinaKey) body.jina_api_key = jinaKey;
    if (openaiBaseUrl !== (setup?.openai_base_url || "")) body.openai_base_url = openaiBaseUrl || null;
    if (telegramToken) body.telegram_token = telegramToken;
    if (telegramAllowedUsers !== (setup?.telegram_allowed_users || "")) {
      body.telegram_allowed_users = telegramAllowedUsers || null;
    }
    if (newPassword) body.web_password = newPassword;

    if (Object.keys(body).length === 0) {
      saveState = "idle";
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
      selectedProvider = (setup!.provider === "openai" ? "openai" : setup!.provider === "anthropic" ? "anthropic" : setup!.anthropic_api_key ? "anthropic" : "openai") as "anthropic" | "openai";
      conversationModel = setup!.conversation_model;
      routineModel = setup!.routine_model;
      openaiBaseUrl = setup!.openai_base_url || "";
      telegramAllowedUsers = setup!.telegram_allowed_users || "";

      // Clear secret inputs after save
      anthropicKey = "";
      openaiKey = "";
      jinaKey = "";
      telegramToken = "";

      if (newPassword) {
        setToken(newPassword);
        newPassword = "";
        newPasswordConfirm = "";
      }

      saveState = "success";
      saveTimeout = setTimeout(() => { saveState = "idle"; saveTimeout = null; }, 3000);
    } catch (e: any) {
      error = e.message;
      saveState = "idle";
    }
  }

  $effect(() => {
    fetchAll();
  });
</script>

<div class="settings-page">
  <header class="settings-header">
    <h1>Settings</h1>
  </header>

  {#if pageState === "loading"}
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

  {#if pageState === "ready" && setup}
    <!-- Configuration -->
    <section class="card">
      <h2>LLM provider</h2>

      <div class="field">
        <span class="field-label">Active provider</span>
        <div class="provider-toggle">
          <button class:selected={selectedProvider === "anthropic"} onclick={() => { selectedProvider = "anthropic"; }}>
            Anthropic
          </button>
          <button class:selected={selectedProvider === "openai"} onclick={() => { selectedProvider = "openai"; }}>
            OpenAI / OpenRouter
          </button>
        </div>
        <small class="field-hint">Determines which API key and model format to use.</small>
      </div>

      <div class="field">
        <label for="conversation-model">Conversation model</label>
        <input id="conversation-model" type="text" bind:value={conversationModel} />
        <small class="field-hint">Used for chat messages that require reasoning.</small>
      </div>

      <div class="field">
        <label for="routine-model">Routine model</label>
        <input id="routine-model" type="text" bind:value={routineModel} />
        <small class="field-hint">Used for scheduled tasks and simple tool follow-ups (cheaper).</small>
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
        <div class="presets">
          {#each [
            ["OpenRouter", "https://openrouter.ai/api/v1"],
            ["Ollama", "http://localhost:11434/v1"],
            ["Groq", "https://api.groq.com/openai/v1"],
            ["Together", "https://api.together.xyz/v1"],
            ["OpenAI", "https://api.openai.com/v1"],
          ] as [name, url]}
            <button class="preset" class:active={openaiBaseUrl === url} onclick={() => { openaiBaseUrl = url; }}>
              {name}
            </button>
          {/each}
        </div>
      </div>
    </section>

    <section class="card">
      <h2>Web search</h2>
      <div class="field">
        <label for="jina-key">Jina API key</label>
        <input id="jina-key" type="password" bind:value={jinaKey}
          placeholder={setup.jina_api_key ? `Current: ${setup.jina_api_key}` : "Not set"} />
        <small class="field-hint">Powers web_read and web_search tools. Get a key at <a href="https://jina.ai" target="_blank" rel="noopener">jina.ai</a>.</small>
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
      <button class="btn primary" onclick={saveConfig} disabled={saveState === "saving"}>
        {saveState === "saving" ? "Saving..." : "Save changes"}
      </button>
      {#if saveState === "success"}
        <span class="save-ok">Saved</span>
      {/if}
    </div>

    <section class="card">
      <h2>Data</h2>
      <p class="data-desc">Export or import all household data (memory, contacts, notes, calendar) as a ZIP archive.</p>
      <div class="data-actions">
        <button class="btn secondary" onclick={exportData} disabled={dataState !== "idle"}>
          {dataState === "exporting" ? "Exporting..." : "Export data"}
        </button>
        <label class="btn secondary import-label" class:disabled={dataState !== "idle"}>
          {dataState === "importing" ? "Importing..." : "Import data"}
          <input type="file" accept=".zip" onchange={importData} disabled={dataState !== "idle"} hidden />
        </label>
      </div>
      {#if dataResult}
        <p class="import-ok">{dataResult}</p>
      {/if}
      {#if dataError}
        <p class="import-err">{dataError}</p>
      {/if}
    </section>
  {/if}
</div>

<style>
  .provider-toggle {
    display: flex;
    gap: 0.5rem;
  }

  .provider-toggle button {
    flex: 1;
    padding: 0.5rem;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: #fdfcfa;
    font-size: 0.82rem;
    font-weight: 500;
    font-family: var(--font-sans);
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
  }

  .provider-toggle button.selected {
    border-color: var(--terracotta);
    color: var(--terracotta);
    background: #fff;
  }

  .field-label {
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text);
  }

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

  .presets {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-top: 0.35rem;
  }

  .preset {
    padding: 0.25rem 0.55rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: #fdfcfa;
    font-size: 0.75rem;
    font-weight: 500;
    font-family: var(--font-sans);
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
  }

  .preset:hover {
    color: var(--text);
    border-color: var(--text-muted);
  }

  .preset.active {
    border-color: var(--terracotta);
    color: var(--terracotta);
    background: #fff;
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

  /* ---- Data section ---- */
  .data-desc {
    font-size: 0.82rem;
    color: var(--text-muted);
    margin: 0 0 0.75rem;
    line-height: 1.4;
  }

  .data-actions {
    display: flex;
    gap: 0.5rem;
  }

  .btn.secondary {
    padding: 0.5rem 1rem;
    border-radius: 8px;
    font-size: 0.82rem;
    font-weight: 500;
    font-family: var(--font-sans);
    cursor: pointer;
    border: 1px solid var(--border);
    background: #fdfcfa;
    color: var(--text);
    transition: all 0.15s;
  }

  .btn.secondary:hover { background: #f0ebe5; }
  .btn.secondary:disabled { opacity: 0.5; cursor: default; }

  .import-label {
    display: inline-flex;
    align-items: center;
  }

  .import-label.disabled {
    opacity: 0.5;
    pointer-events: none;
  }

  .import-ok {
    font-size: 0.82rem;
    color: var(--sage);
    font-weight: 600;
    margin: 0.75rem 0 0;
  }

  .import-err {
    font-size: 0.82rem;
    color: var(--terracotta);
    font-weight: 500;
    margin: 0.75rem 0 0;
  }
</style>

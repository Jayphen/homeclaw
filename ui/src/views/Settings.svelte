<script lang="ts">
  import { api, getToken, setToken } from "$lib/api";

  interface SetupStatus {
    version?: string;
    provider_configured: boolean;
    provider: string | null;
    has_password: boolean;
    model: string;
    anthropic_api_key: string | null;
    openai_api_key: string | null;
    openai_base_url: string | null;
    telegram_configured: boolean;
    telegram_allowed_users: string | null;
    whatsapp_configured: boolean;
    whatsapp_connected: boolean;
    whatsapp_phone_number: string | null;
    whatsapp_allowed_users: string | null;
    jina_api_key: string | null;
    ha_configured: boolean;
    conversation_model: string;
    routine_model: string;
    members?: string[];
    members_with_passwords?: string[];
    admin_members?: string[];
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

  // Log viewer state
  interface LogEntry {
    ts: string;
    level: string;
    logger: string;
    message: string;
  }
  let logEntries: LogEntry[] = $state([]);
  let logLevel: string = $state("all");
  let logExpanded: boolean = $state(false);
  let logLoading: boolean = $state(false);
  let logSearch: string = $state("");
  let logPollTimer: ReturnType<typeof setInterval> | null = $state(null);

  let hiddenLoggers: Set<string> = $state(new Set());

  let loggerCounts = $derived(() => {
    const counts = new Map<string, number>();
    for (const e of logEntries) {
      counts.set(e.logger, (counts.get(e.logger) ?? 0) + 1);
    }
    return counts;
  });

  function toggleLogger(name: string) {
    const next = new Set(hiddenLoggers);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    hiddenLoggers = next;
  }

  let filteredLogEntries = $derived(
    logEntries.filter(e => {
      if (hiddenLoggers.has(e.logger)) return false;
      if (!logSearch) return true;
      const q = logSearch.toLowerCase();
      return e.message.toLowerCase().includes(q) || e.logger.toLowerCase().includes(q);
    })
  );

  async function fetchLogs() {
    logLoading = true;
    try {
      const params = new URLSearchParams();
      params.set("limit", "200");
      if (logLevel !== "all") params.set("level", logLevel);
      const r = await api(`/api/settings/logs?${params}`);
      if (r.ok) logEntries = (await r.json()).entries;
    } catch {}
    logLoading = false;
  }

  function startLogPolling() {
    fetchLogs();
    if (logPollTimer) clearInterval(logPollTimer);
    logPollTimer = setInterval(fetchLogs, 5000);
  }

  function stopLogPolling() {
    if (logPollTimer) { clearInterval(logPollTimer); logPollTimer = null; }
  }

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
  let whatsappEnabled: boolean = $state(false);
  let whatsappConnected: boolean = $state(false);
  let whatsappQrUrl: string | null = $state(null);
  let whatsappQrLoading: boolean = $state(false);
  let whatsappPhoneNumber: string = $state("");
  let whatsappAllowedUsers: string = $state("");
  let timezoneValue: string = $state("");

  // Member account management
  let memberPasswords: Record<string, string> = $state({});
  let memberSaveStatus: Record<string, "idle" | "saving" | "saved" | "error"> = $state({});

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
      whatsappEnabled = setup!.whatsapp_configured;
      whatsappConnected = setup!.whatsapp_connected;
      whatsappPhoneNumber = setup!.whatsapp_phone_number || "";
      whatsappAllowedUsers = setup!.whatsapp_allowed_users || "";
      timezoneValue = setup!.timezone || "";
      if (whatsappEnabled && !whatsappConnected) fetchWhatsAppQr();
      pageState = "ready";
    } catch (e: any) {
      error = e.message;
      pageState = "error";
    }
  }

  async function toggleAdmin(member: string) {
    if (!setup) return;
    const isAdmin = setup.admin_members?.includes(member) ?? false;
    const newAdmins = isAdmin
      ? (setup.admin_members ?? []).filter((m) => m !== member)
      : [...(setup.admin_members ?? []), member];

    // Optimistic update — avoids full re-render and scroll jump
    setup = { ...setup, admin_members: newAdmins };

    try {
      const r = await api("/api/setup/members/admin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ member, is_admin: !isAdmin }),
      });
      if (!r.ok) {
        // Revert on failure
        setup = { ...setup, admin_members: isAdmin
          ? [...newAdmins, member]
          : newAdmins.filter((m) => m !== member) };
      }
    } catch {
      // Revert on error
      setup = { ...setup, admin_members: isAdmin
        ? [...(setup.admin_members ?? []), member]
        : (setup.admin_members ?? []).filter((m) => m !== member) };
    }
  }

  async function saveMemberPassword(member: string) {
    const pw = memberPasswords[member] ?? "";
    memberSaveStatus = { ...memberSaveStatus, [member]: "saving" };
    try {
      const r = await api("/api/setup/members/password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ member, password: pw }),
      });
      if (!r.ok) throw new Error(`${r.status}`);
      memberSaveStatus = { ...memberSaveStatus, [member]: "saved" };
      memberPasswords = { ...memberPasswords, [member]: "" };
      // Refresh to update members_with_passwords
      await fetchAll();
      setTimeout(() => {
        memberSaveStatus = { ...memberSaveStatus, [member]: "idle" };
      }, 2000);
    } catch {
      memberSaveStatus = { ...memberSaveStatus, [member]: "error" };
    }
  }

  async function fetchWhatsAppQr() {
    whatsappQrLoading = true;
    try {
      const r = await api("/api/setup/whatsapp/qr");
      if (r.ok) {
        const blob = await r.blob();
        if (whatsappQrUrl) URL.revokeObjectURL(whatsappQrUrl);
        whatsappQrUrl = URL.createObjectURL(blob);
      } else {
        whatsappQrUrl = null;
      }
    } catch {
      whatsappQrUrl = null;
    }
    whatsappQrLoading = false;
  }

  async function saveConfig() {
    if (saveState === "saving") return;
    error = null;
    if (saveTimeout) { clearTimeout(saveTimeout); saveTimeout = null; }

    saveState = "saving";
    const body: Record<string, string | boolean | null> = {};

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
    if (whatsappEnabled !== setup?.whatsapp_configured) body.whatsapp_enabled = whatsappEnabled;
    if (whatsappPhoneNumber !== (setup?.whatsapp_phone_number || "")) {
      body.whatsapp_phone_number = whatsappPhoneNumber || null;
    }
    if (whatsappAllowedUsers !== (setup?.whatsapp_allowed_users || "")) {
      body.whatsapp_allowed_users = whatsappAllowedUsers || null;
    }
    if (timezoneValue !== (setup?.timezone || "")) body.timezone = timezoneValue || null;

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
      whatsappEnabled = setup!.whatsapp_configured;
      whatsappConnected = setup!.whatsapp_connected;
      whatsappPhoneNumber = setup!.whatsapp_phone_number || "";
      whatsappAllowedUsers = setup!.whatsapp_allowed_users || "";
      timezoneValue = setup!.timezone || "";

      // Clear secret inputs after save
      anthropicKey = "";
      openaiKey = "";
      jinaKey = "";
      telegramToken = "";

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
      <h2>WhatsApp</h2>
      <div class="field">
        <label class="toggle-row">
          <input type="checkbox" bind:checked={whatsappEnabled} />
          <span>Enable WhatsApp channel</span>
        </label>
        <small class="field-hint">
          Connects as a linked device via QR code. Requires <code>homeclaw[whatsapp]</code>.
        </small>
      </div>
      {#if whatsappEnabled}
        <div class="wa-status" class:connected={whatsappConnected}>
          <span class="wa-status-dot"></span>
          {whatsappConnected ? "Connected" : "Not connected"}
        </div>
        {#if !whatsappConnected}
          <div class="wa-qr">
            {#if whatsappQrLoading}
              <p class="wa-qr-hint">Loading QR code...</p>
            {:else if whatsappQrUrl}
              <p class="wa-qr-hint">Scan this QR code with WhatsApp to link this device:</p>
              <img src={whatsappQrUrl} alt="WhatsApp QR code" class="wa-qr-img" />
              <button class="btn secondary" onclick={fetchWhatsAppQr}>Refresh QR</button>
            {:else}
              <p class="wa-qr-hint">No QR code available. Save settings and restart the container to generate one.</p>
            {/if}
          </div>
        {/if}
        <div class="field">
          <label for="wa-phone">Your phone number</label>
          <input id="wa-phone" type="text" bind:value={whatsappPhoneNumber} placeholder="14155551234" />
          <small class="field-hint">
            For pair-code auth (no QR scan needed). Leave blank to use QR code instead.
          </small>
        </div>
        <div class="field">
          <label for="wa-users">Allowed WhatsApp IDs</label>
          <input id="wa-users" type="text" bind:value={whatsappAllowedUsers} placeholder="61412345678, 262899863912491" />
          <small class="field-hint">Comma-separated phone numbers or WhatsApp LIDs. Check logs for the exact ID. Leave blank for unrestricted.</small>
        </div>
      {/if}
    </section>

    <section class="card">
      <h2>Timezone</h2>
      <div class="field">
        <label for="timezone">Timezone</label>
        <input id="timezone" type="text" bind:value={timezoneValue}
          placeholder={Intl.DateTimeFormat().resolvedOptions().timeZone} />
        <small class="field-hint">IANA timezone for schedules and logs (e.g. America/New_York, Europe/London). Leave blank for system default.</small>
      </div>
    </section>

    {#if setup.members && setup.members.length > 0}
      <section class="card">
        <h2>Member accounts</h2>
        <small class="field-hint" style="margin-bottom: 0.75rem; display: block;">
          Set passwords to allow members to log in. Admin members can access settings.
        </small>
        {#each setup.members as member}
          <div class="member-row">
            <span class="member-name">
              {member}
              {#if setup.members_with_passwords?.includes(member)}
                <span class="member-badge">has login</span>
              {/if}
              {#if setup.admin_members?.includes(member)}
                <span class="member-badge admin-badge">admin</span>
              {/if}
            </span>
            <div class="member-controls">
              <label class="admin-toggle">
                <input
                  type="checkbox"
                  checked={setup.admin_members?.includes(member) ?? false}
                  onchange={() => toggleAdmin(member)}
                /> Admin
              </label>
              <div class="member-pw-row">
                <input
                  type="password"
                  bind:value={memberPasswords[member]}
                  placeholder={setup.members_with_passwords?.includes(member) ? "New password (or blank to remove)" : "Set password"}
                />
                <button
                  class="btn secondary"
                  onclick={() => saveMemberPassword(member)}
                  disabled={memberSaveStatus[member] === "saving"}
                >
                  {#if memberSaveStatus[member] === "saving"}
                    Saving...
                  {:else if memberSaveStatus[member] === "saved"}
                    Saved
                  {:else}
                    Set
                  {/if}
                </button>
              </div>
            </div>
            {#if memberSaveStatus[member] === "error"}
              <small class="field-hint" style="color: var(--terracotta);">Failed to update.</small>
            {/if}
          </div>
        {/each}
      </section>
    {/if}

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

    <section class="card">
      <h2
        class="collapsible"
        onclick={() => { logExpanded = !logExpanded; if (logExpanded) startLogPolling(); else stopLogPolling(); }}
        onkeydown={(e: KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { logExpanded = !logExpanded; if (logExpanded) startLogPolling(); else stopLogPolling(); } }}
        role="button"
        tabindex="0"
      >
        <span class="collapse-arrow" class:open={logExpanded}>&#9654;</span>
        Application logs
      </h2>
      {#if logExpanded}
        <div class="log-controls">
          <input type="text" class="log-search" bind:value={logSearch} placeholder="Filter logs..." />
          <select bind:value={logLevel} onchange={fetchLogs}>
            <option value="all">All levels</option>
            <option value="DEBUG">DEBUG</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
          </select>
          <button class="btn secondary" onclick={fetchLogs} disabled={logLoading}>
            {logLoading ? "Loading..." : "Refresh"}
          </button>
        </div>
        {#if loggerCounts().size > 0}
          <div class="log-loggers">
            {#each [...loggerCounts().entries()].sort((a, b) => b[1] - a[1]) as [name, count]}
              <button
                class="logger-pill"
                class:hidden-logger={hiddenLoggers.has(name)}
                onclick={() => toggleLogger(name)}
                title={hiddenLoggers.has(name) ? `Show ${name}` : `Hide ${name}`}
              >
                {name} <span class="logger-count">{count}</span>
              </button>
            {/each}
          </div>
        {/if}
        <div class="log-viewer">
          {#if filteredLogEntries.length === 0}
            <p class="log-empty">{logEntries.length === 0 ? "No log entries." : "No matching entries."}</p>
          {:else}
            {#each filteredLogEntries as entry}
              <div class="log-line">
                <span class="log-ts">{entry.ts.slice(11, 19)}</span>
                <span class="log-level" class:log-error={entry.level === "ERROR"} class:log-warn={entry.level === "WARNING"} class:log-debug={entry.level === "DEBUG"}>{entry.level.slice(0, 4)}</span>
                <span class="log-name">{entry.logger}</span>
                <span class="log-msg">{entry.message}</span>
              </div>
            {/each}
          {/if}
        </div>
      {/if}
    </section>
  {/if}

  {#if setup}
    <p class="version-info">homeclaw v{setup.version ?? "?"}</p>
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

  /* ---- Toggle ---- */
  .toggle-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    margin-bottom: 0;
  }

  .toggle-row input[type="checkbox"] {
    width: 1rem;
    height: 1rem;
    accent-color: var(--terracotta);
    cursor: pointer;
  }

  .toggle-row span {
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--text);
  }

  code {
    font-size: 0.78rem;
    background: rgba(45, 41, 38, 0.06);
    padding: 0.1rem 0.35rem;
    border-radius: 4px;
  }

  /* ---- WhatsApp status & QR ---- */
  .wa-status {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.82rem;
    font-weight: 500;
    color: var(--text-muted);
    margin-bottom: 0.75rem;
  }

  .wa-status.connected { color: var(--sage); }

  .wa-status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--text-muted);
  }

  .wa-status.connected .wa-status-dot { background: var(--sage); }

  .wa-qr {
    margin-bottom: 0.75rem;
  }

  .wa-qr-hint {
    font-size: 0.8rem;
    color: var(--text-muted);
    margin: 0 0 0.5rem;
  }

  .wa-qr-img {
    display: block;
    max-width: 256px;
    border-radius: 8px;
    border: 1px solid var(--border);
    margin-bottom: 0.5rem;
  }

  /* ---- Member accounts ---- */
  .member-row {
    padding: 0.6rem 0;
    border-bottom: 1px solid var(--border);
  }

  .member-row:last-child { border-bottom: none; }

  .member-name {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 0.35rem;
  }

  .member-badge {
    font-size: 0.7rem;
    font-weight: 500;
    color: var(--sage);
    background: rgba(106, 153, 78, 0.1);
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
  }

  .admin-badge {
    color: var(--terracotta);
    background: rgba(180, 100, 60, 0.1);
  }

  .member-controls {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }

  .admin-toggle {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.78rem;
    color: var(--text-muted);
    cursor: pointer;
  }

  .admin-toggle input {
    cursor: pointer;
  }

  .member-pw-row {
    display: flex;
    gap: 0.4rem;
  }

  .member-pw-row input {
    flex: 1;
    padding: 0.45rem 0.65rem;
    border: 1px solid var(--border);
    border-radius: 8px;
    font-size: 0.82rem;
    font-family: var(--font-sans);
    background: #fdfcfa;
    color: var(--text);
  }

  .member-pw-row input:focus {
    outline: none;
    border-color: var(--terracotta);
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

  /* ---- Log viewer ---- */
  .collapsible {
    cursor: pointer;
    user-select: none;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .collapse-arrow {
    font-size: 0.7rem;
    transition: transform 0.15s;
    color: var(--text-muted);
  }

  .collapse-arrow.open {
    transform: rotate(90deg);
  }

  .log-controls {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
  }

  .log-search {
    flex: 1;
    padding: 0.4rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 0.8rem;
    font-family: var(--font-sans);
    background: #fdfcfa;
    color: var(--text);
    min-width: 0;
  }

  .log-search:focus {
    outline: none;
    border-color: var(--terracotta);
  }

  .log-controls select {
    padding: 0.4rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 0.8rem;
    font-family: var(--font-sans);
    background: #fdfcfa;
    color: var(--text);
  }

  .log-loggers {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-bottom: 0.5rem;
  }

  .logger-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.2rem 0.5rem;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: #fdfcfa;
    font-size: 0.7rem;
    font-family: "SF Mono", "Fira Code", monospace;
    color: var(--text);
    cursor: pointer;
    transition: all 0.15s;
  }

  .logger-pill:hover {
    border-color: var(--text-muted);
  }

  .logger-pill.hidden-logger {
    opacity: 0.4;
    text-decoration: line-through;
    background: transparent;
  }

  .logger-count {
    font-size: 0.65rem;
    color: var(--text-muted);
    font-weight: 600;
  }

  .log-viewer {
    max-height: 400px;
    overflow: auto;
    background: #1e1e1e;
    border-radius: 8px;
    padding: 0.75rem;
    font-family: "SF Mono", "Fira Code", "Cascadia Code", monospace;
    font-size: 0.72rem;
    line-height: 1.6;
  }

  .log-empty {
    color: #888;
    margin: 0;
    font-family: var(--font-sans);
    font-size: 0.82rem;
  }

  .log-line {
    display: flex;
    gap: 0.5rem;
    white-space: nowrap;
  }

  .log-line:hover {
    background: rgba(255, 255, 255, 0.04);
  }

  .log-ts {
    color: #666;
    flex-shrink: 0;
  }

  .log-level {
    color: #8bc48a;
    flex-shrink: 0;
    width: 3.2em;
  }

  .log-level.log-error { color: #f07070; }
  .log-level.log-warn { color: #e0a840; }
  .log-level.log-debug { color: #666; }

  .log-name {
    color: #6a9fb5;
    flex-shrink: 0;
    max-width: 18em;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .log-msg {
    color: #d4d4d4;
  }

  .version-info {
    text-align: center;
    font-size: 0.75rem;
    color: var(--text-muted, #999);
    margin-top: 0.5rem;
  }
</style>

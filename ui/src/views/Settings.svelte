<script lang="ts">
  import { api, getToken, setToken } from "$lib/api";
  import type { SetupStatus } from "$lib/types";

  let setup: SetupStatus | null = $state(null);
  let pageState: "loading" | "ready" | "error" = $state("loading");
  let error: string | null = $state(null);

  // ---- Tab navigation ----
  type SettingsTab = "provider" | "channels" | "general" | "members" | "data" | "tool-log";
  let activeTab: SettingsTab = $state("provider");

  // ---- Per-section save state ----
  type SaveState = "idle" | "saving" | "success" | "error";
  let providerSaveState: SaveState = $state("idle");
  let channelsSaveState: SaveState = $state("idle");
  let generalSaveState: SaveState = $state("idle");
  let providerSaveTimeout: ReturnType<typeof setTimeout> | null = null;
  let channelsSaveTimeout: ReturnType<typeof setTimeout> | null = null;
  let generalSaveTimeout: ReturnType<typeof setTimeout> | null = null;

  // ---- Health state ----
  interface HealthData {
    status: string;
    uptime_seconds: number;
    process: { rss_mb: number };
    semantic_memory: { enabled: boolean; index_size_mb?: number };
    channels: { telegram?: boolean; whatsapp?: boolean };
  }
  let health: HealthData | null = $state(null);
  let healthLoading: boolean = $state(false);

  async function fetchHealth() {
    healthLoading = true;
    try {
      const r = await api("/api/health");
      if (r.ok) health = await r.json();
    } catch {}
    healthLoading = false;
  }

  function formatUptime(seconds: number): string {
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (d > 0) return `${d}d ${h}h`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  }

  // ---- Data operation state ----
  let dataState: "idle" | "exporting" | "importing" = $state("idle");
  let dataResult: string | null = $state(null);
  let dataError: string | null = $state(null);

  // ---- Log viewer state ----
  interface LogEntry {
    ts: string;
    level: string;
    logger: string;
    message: string;
    model?: string;
  }
  let logEntries: LogEntry[] = $state([]);
  let logLevel: string = $state("all");
  let logExpanded: boolean = $state(false);
  let logLoading: boolean = $state(false);
  let logSearch: string = $state("");
  let logPollTimer: ReturnType<typeof setInterval> | null = $state(null);
  let logUseFile: boolean = $state(false);

  function defaultAfter(): string {
    const d = new Date(Date.now() - 24 * 60 * 60 * 1000);
    return d.toISOString().slice(0, 16);
  }
  let logAfter: string = $state(defaultAfter());
  let logBefore: string = $state("");

  let hiddenLoggers: Set<string> = $state(new Set());

  let loggerCounts = $derived.by(() => {
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

  // ---- Tool log state ----
  interface ToolLogEntry {
    ts: string;
    tool: string;
    summary: string;
    person: string;
    args: Record<string, string>;
  }
  let toolLogEntries: ToolLogEntry[] = $state([]);
  let toolLogTools: string[] = $state([]);
  let toolLogPersons: string[] = $state([]);
  let toolLogFilterTool: string = $state("");
  let toolLogFilterPerson: string = $state("");
  let toolLogDays: number = $state(7);
  let toolLogLoading: boolean = $state(false);
  let toolLogExpanded: Set<number> = $state(new Set());

  async function fetchToolLog() {
    toolLogLoading = true;
    try {
      const params = new URLSearchParams({ days: String(toolLogDays), limit: "200" });
      if (toolLogFilterTool) params.set("tool", toolLogFilterTool);
      if (toolLogFilterPerson) params.set("person", toolLogFilterPerson);
      const r = await api(`/api/settings/tool-log?${params}`);
      if (r.ok) {
        const data = await r.json();
        toolLogEntries = data.entries;
        toolLogTools = data.tools;
        toolLogPersons = data.persons;
      }
    } catch {}
    toolLogLoading = false;
  }

  function toggleToolLogRow(idx: number) {
    const next = new Set(toolLogExpanded);
    if (next.has(idx)) next.delete(idx);
    else next.add(idx);
    toolLogExpanded = next;
  }

  function buildLogParams(): URLSearchParams {
    const params = new URLSearchParams();
    if (logLevel !== "all") params.set("level", logLevel);
    if (logUseFile) {
      params.set("limit", "2000");
      if (logAfter) params.set("after", new Date(logAfter).toISOString());
      if (logBefore) params.set("before", new Date(logBefore).toISOString());
      if (logSearch) params.set("search", logSearch);
    } else {
      params.set("limit", "200");
    }
    return params;
  }

  async function fetchLogs() {
    logLoading = true;
    try {
      const params = buildLogParams();
      const r = await api(`/api/settings/logs?${params}`);
      if (r.ok) logEntries = (await r.json()).entries;
    } catch {}
    logLoading = false;
  }

  async function downloadLogs() {
    const params = buildLogParams();
    params.set("limit", "10000");
    try {
      const r = await api(`/api/settings/logs/download?${params}`);
      if (!r.ok) return;
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "homeclaw-logs.txt";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {}
  }

  function startLogPolling() {
    fetchLogs();
    if (logPollTimer) clearInterval(logPollTimer);
    logPollTimer = setInterval(fetchLogs, logUseFile ? 15000 : 5000);
  }

  function stopLogPolling() {
    if (logPollTimer) { clearInterval(logPollTimer); logPollTimer = null; }
  }

  // ---- Provider: simple / advanced ----
  type SimpleProvider = "anthropic" | "openai" | "openrouter" | "minimax";
  let providerMode: "simple" | "advanced" = $state("simple");
  let simpleProvider: SimpleProvider = $state("anthropic");
  let simpleApiKey: string = $state("");
  let simpleModel: string = $state("");

  const BASE_URL_PRESETS: Record<"anthropic" | "openai", [string, string][]> = {
    anthropic: [
      ["Anthropic", "https://api.anthropic.com"],
      ["OpenRouter", "https://openrouter.ai/api"],
      ["MiniMax", "https://api.minimax.io/anthropic"],
    ],
    openai: [
      ["OpenRouter", "https://openrouter.ai/api/v1"],
      ["Ollama", "http://localhost:11434/v1"],
      ["Groq", "https://api.groq.com/openai/v1"],
      ["Together", "https://api.together.xyz/v1"],
      ["OpenAI", "https://api.openai.com/v1"],
    ],
  };

  const SIMPLE_PROVIDERS: Record<SimpleProvider, {
    label: string;
    protocol: "anthropic" | "openai";
    baseUrl: string | null;
    keyHint: string;
    modelHint: string;
  }> = {
    anthropic: { label: "Anthropic", protocol: "anthropic", baseUrl: null, keyHint: "sk-ant-...", modelHint: "e.g. claude-sonnet-4-6" },
    openai: { label: "OpenAI", protocol: "openai", baseUrl: null, keyHint: "sk-...", modelHint: "e.g. gpt-4o" },
    openrouter: { label: "OpenRouter", protocol: "openai", baseUrl: "https://openrouter.ai/api/v1", keyHint: "sk-or-...", modelHint: "e.g. anthropic/claude-sonnet-4-6" },
    minimax: { label: "MiniMax", protocol: "openai", baseUrl: "https://api.minimax.io/v1", keyHint: "eyJ...", modelHint: "e.g. MiniMax-M1-80k" },
  };

  let simpleCurrentKey = $derived(
    simpleProvider === "anthropic" ? setup?.anthropic_api_key : setup?.openai_api_key
  );

  function detectSimpleProvider(s: SetupStatus): SimpleProvider {
    const aUrl = s.anthropic_base_url || "";
    const oUrl = s.openai_base_url || "";
    if (aUrl.includes("openrouter") || oUrl.includes("openrouter")) return "openrouter";
    if (aUrl.includes("minimax") || oUrl.includes("minimax")) return "minimax";
    if (s.provider === "anthropic") return "anthropic";
    if (s.provider === "openai") return "openai";
    return s.anthropic_api_key ? "anthropic" : "openai";
  }

  function detectSimpleFromAdvanced(): SimpleProvider {
    if (selectedProvider === "anthropic") {
      if (anthropicBaseUrl.includes("openrouter")) return "openrouter";
      if (anthropicBaseUrl.includes("minimax")) return "minimax";
      return "anthropic";
    }
    if (openaiBaseUrl.includes("openrouter")) return "openrouter";
    if (openaiBaseUrl.includes("minimax")) return "minimax";
    if (!openaiBaseUrl || openaiBaseUrl.includes("openai.com")) return "openai";
    return "openai";
  }

  function switchToSimple() {
    simpleProvider = detectSimpleFromAdvanced();
    simpleModel = conversationModel;
    simpleApiKey = "";
    providerMode = "simple";
  }

  function switchToAdvanced() {
    const cfg = SIMPLE_PROVIDERS[simpleProvider];
    selectedProvider = cfg.protocol;
    conversationModel = simpleModel;
    if (cfg.protocol === "anthropic") {
      anthropicBaseUrl = cfg.baseUrl || "";
    } else {
      openaiBaseUrl = cfg.baseUrl || "";
    }
    if (simpleApiKey) {
      if (cfg.protocol === "anthropic") {
        anthropicKey = simpleApiKey;
      } else {
        openaiKey = simpleApiKey;
      }
      simpleApiKey = "";
    }
    providerMode = "advanced";
  }

  // ---- Advanced mode state ----
  let selectedProvider: "anthropic" | "openai" = $state("anthropic");
  let conversationModel: string = $state("");
  let fastModel: string = $state("");
  let anthropicKey: string = $state("");
  let anthropicBaseUrl: string = $state("");
  let openaiKey: string = $state("");
  let openaiBaseUrl: string = $state("");
  let fastProvider: string = $state("");
  let fastApiKey: string = $state("");
  let fastBaseUrl: string = $state("");
  let visionProvider: string = $state("");
  let visionApiKey: string = $state("");
  let visionBaseUrl: string = $state("");
  let visionModel: string = $state("");
  let effectiveFastProvider = $derived(fastProvider || selectedProvider);
  let effectiveVisionProvider = $derived(visionProvider || selectedProvider);

  // ---- Other config state ----
  let jinaKey: string = $state("");
  let tavilyKey: string = $state("");
  let webReadProvider: string = $state("jina");
  let webReadFallback: string = $state("");
  let webSearchProvider: string = $state("jina");
  let webSearchFallback: string = $state("");
  let telegramToken: string = $state("");
  let telegramAllowedUsers: string = $state("");
  let whatsappEnabled: boolean = $state(false);
  let whatsappConnected: boolean = $state(false);
  let whatsappQrUrl: string | null = $state(null);
  let whatsappQrLoading: boolean = $state(false);
  let whatsappPhoneNumber: string = $state("");
  let whatsappAllowedUsers: string = $state("");
  let timezoneValue: string = $state("");
  let noteDetailLevel: string = $state("normal");

  // ---- Member accounts ----
  let memberPasswords: Record<string, string> = $state({});
  let memberSaveStatus: Record<string, "idle" | "saving" | "saved" | "error"> = $state({});

  // ---- Helpers ----

  function syncFromSetup(s: SetupStatus) {
    setup = s;
    // Advanced mode
    selectedProvider = (s.provider === "openai" ? "openai" : s.provider === "anthropic" ? "anthropic" : s.anthropic_api_key ? "anthropic" : "openai") as "anthropic" | "openai";
    conversationModel = s.conversation_model ?? "";
    fastModel = s.fast_model ?? "";
    anthropicBaseUrl = s.anthropic_base_url || "";
    openaiBaseUrl = s.openai_base_url || "";
    fastProvider = s.fast_provider || "";
    fastBaseUrl = s.fast_base_url || "";
    visionProvider = s.vision_provider || "";
    visionBaseUrl = s.vision_base_url || "";
    visionModel = s.vision_model || "";
    // Provider mode
    providerMode = s.provider_mode === "advanced" ? "advanced" : "simple";
    // Simple mode
    simpleProvider = detectSimpleProvider(s);
    simpleModel = s.conversation_model ?? "";
    // Channels
    telegramAllowedUsers = s.telegram_allowed_users || "";
    whatsappEnabled = s.whatsapp_configured ?? false;
    whatsappConnected = s.whatsapp_connected ?? false;
    whatsappPhoneNumber = s.whatsapp_phone_number || "";
    whatsappAllowedUsers = s.whatsapp_allowed_users || "";
    // General
    timezoneValue = s.timezone || "";
    noteDetailLevel = s.note_detail_level || "normal";
    // Web read
    webReadProvider = s.web_read_provider || "jina";
    webReadFallback = s.web_read_fallback || "";
    webSearchProvider = s.web_search_provider || "jina";
    webSearchFallback = s.web_search_fallback || "";
    // Clear secrets
    anthropicKey = "";
    openaiKey = "";
    fastApiKey = "";
    visionApiKey = "";
    jinaKey = "";
    tavilyKey = "";
    telegramToken = "";
    simpleApiKey = "";
  }

  async function postSetup(body: Record<string, string | boolean | null>): Promise<SetupStatus> {
    const r = await api("/api/setup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const data = await r.json().catch(() => null);
      throw new Error(data?.detail || `Error ${r.status}`);
    }
    return await r.json();
  }

  // ---- Data operations ----

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

  // ---- Fetch ----

  async function fetchAll() {
    pageState = "loading";
    error = null;
    try {
      const setupRes = await api("/api/setup/status");
      if (!setupRes.ok) throw new Error(`${setupRes.status}`);
      const s: SetupStatus = await setupRes.json();
      syncFromSetup(s);
      if (whatsappEnabled && !whatsappConnected) fetchWhatsAppQr();
      pageState = "ready";
    } catch (e: any) {
      error = e.message;
      pageState = "error";
    }
  }

  // ---- Save: Provider ----

  async function saveProvider() {
    if (providerSaveState === "saving") return;
    error = null;
    if (providerSaveTimeout) { clearTimeout(providerSaveTimeout); providerSaveTimeout = null; }

    const body: Record<string, string | boolean | null> = {};

    if (providerMode === "simple") {
      const cfg = SIMPLE_PROVIDERS[simpleProvider];
      if (cfg.protocol !== setup?.provider) body.provider = cfg.protocol;
      if (simpleModel !== (setup?.conversation_model ?? "")) body.conversation_model = simpleModel;
      if (simpleApiKey) {
        if (cfg.protocol === "anthropic") body.anthropic_api_key = simpleApiKey;
        else body.openai_api_key = simpleApiKey;
      }
      const curUrl = cfg.protocol === "anthropic"
        ? (setup?.anthropic_base_url || "")
        : (setup?.openai_base_url || "");
      const targetUrl = cfg.baseUrl || "";
      if (targetUrl !== curUrl) {
        if (cfg.protocol === "anthropic") body.anthropic_base_url = cfg.baseUrl;
        else body.openai_base_url = cfg.baseUrl;
      }
    } else {
      if (selectedProvider !== setup?.provider) body.provider = selectedProvider;
      if (conversationModel !== (setup?.conversation_model ?? "")) body.conversation_model = conversationModel;
      if (fastModel !== (setup?.fast_model ?? "")) body.fast_model = fastModel;
      if (anthropicKey) body.anthropic_api_key = anthropicKey;
      if (anthropicBaseUrl !== (setup?.anthropic_base_url || "")) body.anthropic_base_url = anthropicBaseUrl || null;
      if (openaiKey) body.openai_api_key = openaiKey;
      if (openaiBaseUrl !== (setup?.openai_base_url || "")) body.openai_base_url = openaiBaseUrl || null;
      if (fastProvider !== (setup?.fast_provider || "")) body.fast_provider = fastProvider || null;
      if (fastApiKey) body.fast_api_key = fastApiKey;
      if (fastBaseUrl !== (setup?.fast_base_url || "")) body.fast_base_url = fastBaseUrl || null;
      if (visionProvider !== (setup?.vision_provider || "")) body.vision_provider = visionProvider || null;
      if (visionApiKey) body.vision_api_key = visionApiKey;
      if (visionBaseUrl !== (setup?.vision_base_url || "")) body.vision_base_url = visionBaseUrl || null;
      if (visionModel !== (setup?.vision_model || "")) body.vision_model = visionModel || null;
    }

    body.provider_mode = providerMode;

    if (Object.keys(body).length === 0) { providerSaveState = "idle"; return; }

    providerSaveState = "saving";
    try {
      const result = await postSetup(body);
      syncFromSetup(result);
      providerSaveState = "success";
      providerSaveTimeout = setTimeout(() => { providerSaveState = "idle"; }, 3000);
    } catch (e: any) {
      error = e.message;
      providerSaveState = "idle";
    }
  }

  // ---- Save: Channels ----

  async function saveChannels() {
    if (channelsSaveState === "saving") return;
    error = null;
    if (channelsSaveTimeout) { clearTimeout(channelsSaveTimeout); channelsSaveTimeout = null; }

    const body: Record<string, string | boolean | null> = {};
    if (jinaKey) body.jina_api_key = jinaKey;
    if (tavilyKey) body.tavily_api_key = tavilyKey;
    if (webReadProvider !== (setup?.web_read_provider || "jina")) {
      body.web_read_provider = webReadProvider;
    }
    if (webReadFallback !== (setup?.web_read_fallback || "")) {
      body.web_read_fallback = webReadFallback || null;
    }
    if (webSearchProvider !== (setup?.web_search_provider || "jina")) {
      body.web_search_provider = webSearchProvider;
    }
    if (webSearchFallback !== (setup?.web_search_fallback || "")) {
      body.web_search_fallback = webSearchFallback || null;
    }
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

    if (Object.keys(body).length === 0) { channelsSaveState = "idle"; return; }

    channelsSaveState = "saving";
    try {
      const result = await postSetup(body);
      syncFromSetup(result);
      if (whatsappEnabled && !whatsappConnected) fetchWhatsAppQr();
      channelsSaveState = "success";
      channelsSaveTimeout = setTimeout(() => { channelsSaveState = "idle"; }, 3000);
    } catch (e: any) {
      error = e.message;
      channelsSaveState = "idle";
    }
  }

  // ---- Save: General ----

  async function saveGeneral() {
    if (generalSaveState === "saving") return;
    error = null;
    if (generalSaveTimeout) { clearTimeout(generalSaveTimeout); generalSaveTimeout = null; }

    const body: Record<string, string | boolean | null> = {};
    if (timezoneValue !== (setup?.timezone || "")) body.timezone = timezoneValue || null;
    if (noteDetailLevel !== (setup?.note_detail_level || "normal")) body.note_detail_level = noteDetailLevel;

    if (Object.keys(body).length === 0) { generalSaveState = "idle"; return; }

    generalSaveState = "saving";
    try {
      const result = await postSetup(body);
      syncFromSetup(result);
      generalSaveState = "success";
      generalSaveTimeout = setTimeout(() => { generalSaveState = "idle"; }, 3000);
    } catch (e: any) {
      error = e.message;
      generalSaveState = "idle";
    }
  }

  // ---- WhatsApp ----

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

  // ---- Members ----

  async function toggleAdmin(member: string) {
    if (!setup) return;
    const isAdmin = setup.admin_members?.includes(member) ?? false;
    const newAdmins = isAdmin
      ? (setup.admin_members ?? []).filter((m) => m !== member)
      : [...(setup.admin_members ?? []), member];

    setup = { ...setup, admin_members: newAdmins };

    try {
      const r = await api("/api/setup/members/admin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ member, is_admin: !isAdmin }),
      });
      if (!r.ok) {
        setup = { ...setup, admin_members: isAdmin
          ? [...newAdmins, member]
          : newAdmins.filter((m) => m !== member) };
      }
    } catch {
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
      await fetchAll();
      setTimeout(() => {
        memberSaveStatus = { ...memberSaveStatus, [member]: "idle" };
      }, 2000);
    } catch {
      memberSaveStatus = { ...memberSaveStatus, [member]: "error" };
    }
  }

  // ---- Init ----

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
    <nav class="settings-nav">
      <button class:active={activeTab === "provider"} onclick={() => { activeTab = "provider"; }}>Provider</button>
      <button class:active={activeTab === "channels"} onclick={() => { activeTab = "channels"; }}>Channels</button>
      <button class:active={activeTab === "general"} onclick={() => { activeTab = "general"; fetchHealth(); }}>General</button>
      {#if setup.members && setup.members.length > 0}
        <button class:active={activeTab === "members"} onclick={() => { activeTab = "members"; }}>Members</button>
      {/if}
      <button class:active={activeTab === "data"} onclick={() => { activeTab = "data"; }}>Data</button>
      <button class:active={activeTab === "tool-log"} onclick={() => { activeTab = "tool-log"; fetchToolLog(); }}>Tool Log</button>
    </nav>

    <!-- ============ PROVIDER TAB ============ -->
    {#if activeTab === "provider"}
      <section class="card">
        <div class="card-header">
          <h2>LLM provider</h2>
          <div class="mode-toggle">
            <button class:active={providerMode === "simple"} onclick={switchToSimple}>Simple</button>
            <button class:active={providerMode === "advanced"} onclick={switchToAdvanced}>Advanced</button>
          </div>
        </div>

        {#if providerMode === "simple"}
          <div class="field">
            <span class="field-label">Provider</span>
            <div class="provider-grid">
              {#each (["anthropic", "openai", "openrouter", "minimax"] as SimpleProvider[]) as p}
                <button class:selected={simpleProvider === p} onclick={() => { simpleProvider = p; }}>
                  {SIMPLE_PROVIDERS[p].label}
                </button>
              {/each}
            </div>
          </div>

          <div class="field">
            <label for="simple-key">API key</label>
            <input id="simple-key" type="password" bind:value={simpleApiKey}
              placeholder={simpleCurrentKey ? `Current: ${simpleCurrentKey}` : SIMPLE_PROVIDERS[simpleProvider].keyHint} />
          </div>

          <div class="field">
            <label for="simple-model">Model</label>
            <input id="simple-model" type="text" bind:value={simpleModel}
              placeholder={SIMPLE_PROVIDERS[simpleProvider].modelHint} />
          </div>

        {:else}
          <!-- ---- Main model ---- -->
          <h3 class="subsection">Main model</h3>

          <div class="field">
            <span class="field-label">Protocol</span>
            <div class="provider-toggle">
              <button class:selected={selectedProvider === "anthropic"} onclick={() => { selectedProvider = "anthropic"; }}>
                Anthropic
              </button>
              <button class:selected={selectedProvider === "openai"} onclick={() => { selectedProvider = "openai"; }}>
                OpenAI
              </button>
            </div>
          </div>

          <div class="field">
            <label for="conversation-model">Model</label>
            <input id="conversation-model" type="text" bind:value={conversationModel} />
          </div>

          {#if selectedProvider === "anthropic"}
            <div class="field">
              <label for="anthropic-key">API key</label>
              <input id="anthropic-key" type="password" bind:value={anthropicKey}
                placeholder={setup.anthropic_api_key ? `Current: ${setup.anthropic_api_key}` : "Not set"} />
            </div>
            <div class="field">
              <label for="anthropic-base-url">Base URL</label>
              <input id="anthropic-base-url" type="url" bind:value={anthropicBaseUrl} placeholder="https://api.anthropic.com (default)" />
              <div class="presets">
                {#each BASE_URL_PRESETS.anthropic as [name, url]}
                  <button class="preset" class:active={anthropicBaseUrl === url} onclick={() => { anthropicBaseUrl = url; }}>
                    {name}
                  </button>
                {/each}
              </div>
            </div>
          {:else}
            <div class="field">
              <label for="openai-key">API key</label>
              <input id="openai-key" type="password" bind:value={openaiKey}
                placeholder={setup.openai_api_key ? `Current: ${setup.openai_api_key}` : "Not set"} />
            </div>
            <div class="field">
              <label for="openai-base-url">Base URL</label>
              <input id="openai-base-url" type="url" bind:value={openaiBaseUrl} placeholder="https://openrouter.ai/api/v1" />
              <div class="presets">
                {#each BASE_URL_PRESETS.openai as [name, url]}
                  <button class="preset" class:active={openaiBaseUrl === url} onclick={() => { openaiBaseUrl = url; }}>
                    {name}
                  </button>
                {/each}
              </div>
            </div>
          {/if}

          <!-- ---- Fast model ---- -->
          <h3 class="subsection">Fast model</h3>

          <div class="field">
            <label for="fast-model">Model</label>
            <input id="fast-model" type="text" bind:value={fastModel} placeholder="Same as main" />
            <small class="field-hint">Used for simple tool follow-ups (cheaper/faster).</small>
          </div>

          <div class="field">
            <span class="field-label">Provider</span>
            <div class="toggle-group">
              <button class:active={!fastProvider} onclick={() => { fastProvider = ""; }}>
                Same as main
              </button>
              <button class:active={fastProvider === "anthropic"} onclick={() => { fastProvider = "anthropic"; }}>
                Anthropic
              </button>
              <button class:active={fastProvider === "openai"} onclick={() => { fastProvider = "openai"; }}>
                OpenAI
              </button>
            </div>
          </div>

          {#if fastProvider}
          <div class="field">
            <label for="fast-api-key">API key</label>
            <input id="fast-api-key" type="password" bind:value={fastApiKey}
              placeholder={setup.fast_api_key ? `Current: ${setup.fast_api_key}` : "Falls back to main key"} />
          </div>

          <div class="field">
            <label for="fast-base-url">Base URL</label>
            <input id="fast-base-url" type="url" bind:value={fastBaseUrl} placeholder="Falls back to main URL" />
            <div class="presets">
              {#each BASE_URL_PRESETS[effectiveFastProvider] as [name, url]}
                <button class="preset" class:active={fastBaseUrl === url} onclick={() => { fastBaseUrl = url; }}>
                  {name}
                </button>
              {/each}
            </div>
          </div>
          {/if}

          <!-- ---- Vision model ---- -->
          <h3 class="subsection">Vision model</h3>

          <div class="field">
            <label for="vision-model">Model</label>
            <input id="vision-model" type="text" bind:value={visionModel} placeholder="Same as main" />
            <small class="field-hint">Only needed if your main provider doesn't support image input.</small>
          </div>

          <div class="field">
            <span class="field-label">Provider</span>
            <div class="toggle-group">
              <button class:active={!visionProvider} onclick={() => { visionProvider = ""; }}>
                Same as main
              </button>
              <button class:active={visionProvider === "anthropic"} onclick={() => { visionProvider = "anthropic"; }}>
                Anthropic
              </button>
              <button class:active={visionProvider === "openai"} onclick={() => { visionProvider = "openai"; }}>
                OpenAI
              </button>
            </div>
          </div>

          {#if visionProvider}
          <div class="field">
            <label for="vision-api-key">API key</label>
            <input id="vision-api-key" type="password" bind:value={visionApiKey}
              placeholder={setup.vision_api_key ? `Current: ${setup.vision_api_key}` : "Falls back to main key"} />
          </div>

          <div class="field">
            <label for="vision-base-url">Base URL</label>
            <input id="vision-base-url" type="url" bind:value={visionBaseUrl} placeholder="Falls back to main URL" />
            <div class="presets">
              {#each BASE_URL_PRESETS[effectiveVisionProvider] as [name, url]}
                <button class="preset" class:active={visionBaseUrl === url} onclick={() => { visionBaseUrl = url; }}>
                  {name}
                </button>
              {/each}
            </div>
          </div>
          {/if}
        {/if}

        <div class="section-save">
          <button class="btn primary" onclick={saveProvider} disabled={providerSaveState === "saving"}>
            {providerSaveState === "saving" ? "Saving..." : "Save"}
          </button>
          {#if providerSaveState === "success"}
            <span class="save-ok">Saved</span>
          {/if}
        </div>
      </section>

    <!-- ============ CHANNELS TAB ============ -->
    {:else if activeTab === "channels"}
      <section class="card">
        <h2>Web search &amp; read</h2>
        <div class="field">
          <label for="jina-key">Jina API key</label>
          <input id="jina-key" type="password" bind:value={jinaKey}
            placeholder={setup.jina_api_key ? `Current: ${setup.jina_api_key}` : "Not set"} />
          <small class="field-hint">Powers web_search and web_read (Jina provider). Get a key at <a href="https://jina.ai" target="_blank" rel="noopener noreferrer">jina.ai</a>.</small>
        </div>
        <div class="field">
          <label for="tavily-key">Tavily API key</label>
          <input id="tavily-key" type="password" bind:value={tavilyKey}
            placeholder={setup.tavily_api_key ? `Current: ${setup.tavily_api_key}` : "Not set"} />
          <small class="field-hint">Alternative provider for web_search and web_read. Get a key at <a href="https://tavily.com" target="_blank" rel="noopener noreferrer">tavily.com</a>.</small>
        </div>
        <div class="field">
          <label for="web-read-provider">web_read provider</label>
          <select id="web-read-provider" bind:value={webReadProvider}>
            {#each (setup.available_read_providers || ["jina", "tavily"]) as p}
              <option value={p}>{p}</option>
            {/each}
          </select>
          <small class="field-hint">Primary provider for fetching web page content.</small>
        </div>
        <div class="field">
          <label for="web-read-fallback">web_read fallback</label>
          <select id="web-read-fallback" bind:value={webReadFallback}>
            <option value="">None</option>
            {#each (setup.available_read_providers || ["jina", "tavily"]) as p}
              <option value={p}>{p}</option>
            {/each}
          </select>
          <small class="field-hint">Used when the primary provider fails or returns low-quality content.</small>
        </div>
        <div class="field">
          <label for="web-search-provider">web_search provider</label>
          <select id="web-search-provider" bind:value={webSearchProvider}>
            {#each (setup.available_search_providers || ["jina", "tavily"]) as p}
              <option value={p}>{p}</option>
            {/each}
          </select>
          <small class="field-hint">Primary provider for web search queries.</small>
        </div>
        <div class="field">
          <label for="web-search-fallback">web_search fallback</label>
          <select id="web-search-fallback" bind:value={webSearchFallback}>
            <option value="">None</option>
            {#each (setup.available_search_providers || ["jina", "tavily"]) as p}
              <option value={p}>{p}</option>
            {/each}
          </select>
          <small class="field-hint">Used when the primary search provider fails or runs out of credits.</small>
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

      <div class="section-save">
        <button class="btn primary" onclick={saveChannels} disabled={channelsSaveState === "saving"}>
          {channelsSaveState === "saving" ? "Saving..." : "Save"}
        </button>
        {#if channelsSaveState === "success"}
          <span class="save-ok">Saved</span>
        {/if}
      </div>

    <!-- ============ GENERAL TAB ============ -->
    {:else if activeTab === "general"}
      <section class="card">
        <h2>System status</h2>
        {#if healthLoading && !health}
          <p class="field-hint">Loading...</p>
        {:else if health}
          <div class="health-grid">
            <div class="health-item">
              <span class="health-label">Status</span>
              <span class="health-value">
                <span class="health-dot" class:health-ok={health.status === "ok"}></span>
                {health.status}
              </span>
            </div>
            <div class="health-item">
              <span class="health-label">Uptime</span>
              <span class="health-value">{formatUptime(health.uptime_seconds)}</span>
            </div>
            <div class="health-item">
              <span class="health-label">Memory</span>
              <span class="health-value">{health.process.rss_mb} MB</span>
            </div>
            <div class="health-item">
              <span class="health-label">Semantic search</span>
              <span class="health-value">
                <span class="health-dot" class:health-ok={health.semantic_memory.enabled}></span>
                {health.semantic_memory.enabled ? "active" : "off"}
                {#if health.semantic_memory.index_size_mb != null}
                  <span class="health-detail">({health.semantic_memory.index_size_mb} MB)</span>
                {/if}
              </span>
            </div>
            {#if health.channels.telegram != null}
              <div class="health-item">
                <span class="health-label">Telegram</span>
                <span class="health-value">
                  <span class="health-dot" class:health-ok={health.channels.telegram}></span>
                  {health.channels.telegram ? "configured" : "off"}
                </span>
              </div>
            {/if}
            {#if health.channels.whatsapp != null}
              <div class="health-item">
                <span class="health-label">WhatsApp</span>
                <span class="health-value">
                  <span class="health-dot" class:health-ok={health.channels.whatsapp}></span>
                  {health.channels.whatsapp ? "connected" : "off"}
                </span>
              </div>
            {/if}
          </div>
        {:else}
          <p class="field-hint">Could not load system status.</p>
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

      <section class="card">
        <h2>Note-taking</h2>
        <div class="field">
          <label for="note-detail-level">Detail level</label>
          <select id="note-detail-level" bind:value={noteDetailLevel}>
            <option value="minimal">Minimal — only major events</option>
            <option value="normal">Normal — notable things</option>
            <option value="detailed">Detailed — comprehensive daily journal</option>
          </select>
          <small class="field-hint">Controls how aggressively homeclaw saves daily notes. Requires restart.</small>
        </div>
      </section>

      <div class="section-save">
        <button class="btn primary" onclick={saveGeneral} disabled={generalSaveState === "saving"}>
          {generalSaveState === "saving" ? "Saving..." : "Save"}
        </button>
        {#if generalSaveState === "success"}
          <span class="save-ok">Saved</span>
        {/if}
      </div>

    <!-- ============ MEMBERS TAB ============ -->
    {:else if activeTab === "members"}
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
                <small class="field-hint" style="color: var(--secondary);">Failed to update.</small>
              {/if}
            </div>
          {/each}
        </section>
      {:else}
        <section class="card">
          <h2>Member accounts</h2>
          <p class="field-hint">No household members registered yet. Members are created when they register via Telegram or WhatsApp.</p>
        </section>
      {/if}

    <!-- ============ DATA TAB ============ -->
    {:else if activeTab === "data"}
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
            <label class="log-toggle">
              <input type="checkbox" bind:checked={logUseFile} onchange={() => { fetchLogs(); if (logPollTimer) startLogPolling(); }} />
              <span>File</span>
            </label>
            <button class="btn secondary" onclick={fetchLogs} disabled={logLoading}>
              {logLoading ? "Loading..." : "Refresh"}
            </button>
            <button class="btn secondary" onclick={downloadLogs} title="Download filtered logs">
              Download
            </button>
          </div>
          {#if logUseFile}
            <div class="log-date-range">
              <label>
                After
                <input type="datetime-local" bind:value={logAfter} onchange={fetchLogs} />
              </label>
              <label>
                Before
                <input type="datetime-local" bind:value={logBefore} onchange={fetchLogs} />
              </label>
            </div>
          {/if}
          {#if loggerCounts.size > 0}
            <div class="log-loggers">
              {#each [...loggerCounts.entries()].sort((a, b) => b[1] - a[1]) as [name, count]}
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
                  {#if entry.model}<span class="log-model">{entry.model}</span>{/if}
                  <span class="log-msg">{entry.message}</span>
                </div>
              {/each}
            {/if}
          </div>
        {/if}
      </section>
    {:else if activeTab === "tool-log"}
      <section class="card">
        <h2>Tool call log</h2>
        <p class="data-desc">Every tool call the agent makes, with full arguments. Use this to debug unexpected behavior like misrouted memory saves.</p>

        <div class="tl-controls">
          <select bind:value={toolLogDays} onchange={fetchToolLog}>
            <option value={1}>Last 24h</option>
            <option value={3}>Last 3 days</option>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
          </select>
          <select bind:value={toolLogFilterTool} onchange={fetchToolLog}>
            <option value="">All tools</option>
            {#each toolLogTools as t}
              <option value={t}>{t}</option>
            {/each}
          </select>
          <select bind:value={toolLogFilterPerson} onchange={fetchToolLog}>
            <option value="">All people</option>
            {#each toolLogPersons as p}
              <option value={p}>{p}</option>
            {/each}
          </select>
          <button class="btn secondary" onclick={fetchToolLog} disabled={toolLogLoading}>
            {toolLogLoading ? "Loading..." : "Refresh"}
          </button>
        </div>

        {#if toolLogEntries.length === 0}
          <p class="log-empty">{toolLogLoading ? "Loading..." : "No tool calls found."}</p>
        {:else}
          <div class="tl-list">
            {#each toolLogEntries as entry, idx}
              <div class="tl-row" class:tl-household={entry.args.person === "household"}>
                <button class="tl-header" onclick={() => toggleToolLogRow(idx)}>
                  <span class="tl-arrow" class:open={toolLogExpanded.has(idx)}>&#9654;</span>
                  <span class="tl-tool">{entry.tool}</span>
                  <span class="tl-summary">{entry.summary}</span>
                  <span class="tl-person">{entry.person}</span>
                  <span class="tl-time">{new Date(entry.ts).toLocaleString()}</span>
                </button>
                {#if toolLogExpanded.has(idx)}
                  <div class="tl-args">
                    <table>
                      <thead><tr><th>Param</th><th>Value</th></tr></thead>
                      <tbody>
                        {#each Object.entries(entry.args) as [key, val]}
                          <tr>
                            <td class="tl-arg-key">{key}</td>
                            <td class="tl-arg-val">{val}</td>
                          </tr>
                        {/each}
                      </tbody>
                    </table>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
          <p class="tl-total">{toolLogEntries.length} entries</p>
        {/if}
      </section>
    {/if}
  {/if}

  {#if setup}
    <p class="version-info">homeclaw v{setup.version ?? "?"}</p>
  {/if}
</div>

<style>
  /* ---- Layout ---- */
  .settings-page {
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

  /* ---- Tab navigation ---- */
  .settings-nav {
    display: flex;
    gap: 0.25rem;
    background: var(--surface);
    border-radius: var(--radius);
    padding: 0.25rem;
    position: sticky;
    top: 0;
    z-index: 10;
    overflow-x: auto;
  }

  .settings-nav button {
    flex: 1;
    padding: 0.5rem 0.75rem;
    border: none;
    border-radius: var(--radius-md);
    background: transparent;
    font-size: 0.82rem;
    font-weight: 500;
    font-family: var(--font-sans);
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
    white-space: nowrap;
  }

  .settings-nav button:hover {
    color: var(--text);
  }

  .settings-nav button.active {
    background: var(--primary);
    color: #fff;
  }

  /* ---- Cards ---- */
  .card {
    background: var(--surface);
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

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
  }

  .card-header h2 {
    margin: 0;
  }

  /* ---- Mode toggle (Simple / Advanced) ---- */
  .mode-toggle {
    display: flex;
    gap: 0.2rem;
    background: var(--surface-low);
    border-radius: var(--radius-md);
    padding: 0.2rem;
  }

  .mode-toggle button {
    padding: 0.3rem 0.65rem;
    border: none;
    border-radius: calc(var(--radius-md) - 2px);
    background: transparent;
    font-size: 0.75rem;
    font-weight: 500;
    font-family: var(--font-sans);
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
  }

  .mode-toggle button.active {
    background: var(--surface);
    color: var(--text);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
  }

  /* ---- Simple provider grid ---- */
  .provider-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.5rem;
  }

  .provider-grid button {
    padding: 0.55rem 0.5rem;
    border: none;
    border-radius: var(--radius-md);
    background: var(--surface-low);
    font-size: 0.82rem;
    font-weight: 500;
    font-family: var(--font-sans);
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
  }

  .provider-grid button.selected {
    color: #fff;
    background: var(--primary);
  }

  /* ---- Advanced subsection headers ---- */
  .subsection {
    font-family: var(--font-sans);
    font-weight: 600;
    font-size: 0.82rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin: 1.25rem 0 0.5rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
  }

  .subsection:first-of-type {
    margin-top: 0;
    padding-top: 0;
    border-top: none;
  }

  /* ---- Provider toggle (Anthropic / OpenAI) ---- */
  .provider-toggle {
    display: flex;
    gap: 0.5rem;
  }

  .provider-toggle button {
    flex: 1;
    padding: 0.5rem;
    border: none;
    border-radius: var(--radius-md);
    background: var(--surface-low);
    font-size: 0.82rem;
    font-weight: 500;
    font-family: var(--font-sans);
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
  }

  .provider-toggle button.selected {
    color: #fff;
    background: var(--primary);
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

  .field-label {
    display: block;
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 0.3rem;
  }

  .field input,
  .field select {
    width: 100%;
    padding: 0.55rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    font-size: 0.85rem;
    font-family: var(--font-sans);
    background: var(--surface-low);
    color: var(--text);
    transition: border-color 0.15s;
  }

  .field input:focus,
  .field select:focus {
    outline: none;
    border-color: var(--primary);
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
    border: none;
    border-radius: var(--radius-sm);
    background: var(--surface-low);
    font-size: 0.75rem;
    font-weight: 500;
    font-family: var(--font-sans);
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
  }

  .preset:hover {
    color: var(--text);
  }

  .preset.active {
    color: #fff;
    background: var(--primary);
  }

  .toggle-group {
    display: flex;
    gap: 0.5rem;
  }

  .toggle-group button {
    flex: 1;
    padding: 0.5rem;
    border: none;
    border-radius: var(--radius-md);
    background: var(--surface-low);
    font-size: 0.82rem;
    font-weight: 500;
    font-family: var(--font-sans);
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
  }

  .toggle-group button.active {
    color: #fff;
    background: var(--primary);
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
    accent-color: var(--primary);
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
    border-radius: var(--radius-sm);
  }

  /* ---- Section save row ---- */
  .section-save {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-top: 0.75rem;
  }

  .card .section-save {
    margin-top: 1rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--border);
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
    border-radius: var(--radius-sm);
    margin-bottom: 0.5rem;
  }

  /* ---- Member accounts ---- */
  .member-row {
    padding: 0.6rem 0;
  }

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
    color: var(--primary);
    background: var(--surface-low);
    padding: 0.1rem 0.4rem;
    border-radius: var(--radius-sm);
  }

  .admin-badge {
    color: var(--secondary);
    background: var(--surface-low);
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
    border-radius: var(--radius-md);
    font-size: 0.82rem;
    font-family: var(--font-sans);
    background: var(--surface-low);
    color: var(--text);
  }

  .member-pw-row input:focus {
    outline: none;
    border-color: var(--primary);
  }

  /* ---- Buttons ---- */
  .btn.primary {
    padding: 0.55rem 1.25rem;
    border-radius: var(--radius-pill);
    font-size: 0.85rem;
    font-weight: 600;
    font-family: var(--font-sans);
    cursor: pointer;
    border: none;
    background: var(--primary);
    color: #fff;
    transition: filter 0.15s;
  }

  .btn.primary:hover { filter: brightness(1.08); }
  .btn.primary:disabled { opacity: 0.5; cursor: default; }

  .btn.secondary {
    padding: 0.5rem 1rem;
    border-radius: var(--radius-pill);
    font-size: 0.82rem;
    font-weight: 500;
    font-family: var(--font-sans);
    cursor: pointer;
    border: none;
    background: var(--surface-low);
    color: var(--text);
    transition: all 0.15s;
  }

  .btn.secondary:hover { filter: brightness(0.95); }
  .btn.secondary:disabled { opacity: 0.5; cursor: default; }

  .save-ok {
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--sage);
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
    background: var(--primary);
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
    border-radius: var(--radius);
    padding: 1rem 1.25rem;
    color: var(--secondary);
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .error-card p { margin: 0; font-weight: 500; font-size: 0.85rem; }
  .error-card small { color: var(--text-muted); font-size: 0.8rem; }

  .dismiss {
    margin-left: auto;
    padding: 0.3rem 0.6rem;
    border: none;
    border-radius: var(--radius-pill);
    background: var(--surface-low);
    color: var(--secondary);
    font-size: 0.78rem;
    font-weight: 500;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: filter 0.15s;
  }

  .dismiss:hover { filter: brightness(0.95); }

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
    color: var(--secondary);
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
    border-radius: var(--radius-md);
    font-size: 0.8rem;
    font-family: var(--font-sans);
    background: var(--surface-low);
    color: var(--text);
    min-width: 0;
  }

  .log-search:focus {
    outline: none;
    border-color: var(--primary);
  }

  .log-toggle {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.78rem;
    color: var(--text-muted);
    cursor: pointer;
    white-space: nowrap;
  }

  .log-toggle input {
    cursor: pointer;
    accent-color: var(--primary);
  }

  .log-date-range {
    display: flex;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
  }

  .log-date-range label {
    font-size: 0.75rem;
    color: var(--text-muted);
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }

  .log-date-range input {
    padding: 0.3rem 0.5rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    font-size: 0.75rem;
    font-family: var(--font-sans);
    background: var(--surface-low);
    color: var(--text);
  }

  .log-date-range input:focus {
    outline: none;
    border-color: var(--primary);
  }

  .log-controls select {
    padding: 0.4rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    font-size: 0.8rem;
    font-family: var(--font-sans);
    background: var(--surface-low);
    color: var(--text);
    transition: border-color 0.15s;
  }

  .log-controls select:focus {
    outline: none;
    border-color: var(--primary);
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
    border: none;
    border-radius: var(--radius-pill);
    background: var(--surface-low);
    font-size: 0.7rem;
    font-family: "SF Mono", "Fira Code", monospace;
    color: var(--text);
    cursor: pointer;
    transition: all 0.15s;
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
    border-radius: var(--radius-sm);
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

  .log-model {
    color: #c9a0dc;
    font-size: 0.8em;
    background: rgba(201, 160, 220, 0.1);
    padding: 0 0.35em;
    border-radius: 3px;
    flex-shrink: 0;
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

  /* ---- System health ---- */
  .health-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.6rem 1.5rem;
  }

  .health-item {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
  }

  .health-label {
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .health-value {
    font-size: 0.88rem;
    font-weight: 500;
    color: var(--text);
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }

  .health-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--text-muted);
    flex-shrink: 0;
  }

  .health-dot.health-ok {
    background: var(--sage);
  }

  .health-detail {
    font-size: 0.78rem;
    color: var(--text-muted);
    font-weight: 400;
  }

  /* ---- Tool Log ---- */
  .tl-controls {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin-bottom: 1rem;
  }

  .tl-controls select {
    font-size: 0.82rem;
    padding: 0.35rem 0.5rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--surface);
    color: var(--text);
  }

  .tl-list {
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .tl-row {
    border-bottom: 1px solid var(--surface-low);
  }

  .tl-row.tl-household {
    border-left: 3px solid var(--sage);
  }

  .tl-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    width: 100%;
    padding: 0.5rem 0.6rem;
    border: none;
    background: none;
    cursor: pointer;
    text-align: left;
    font-family: inherit;
    font-size: 0.82rem;
    color: var(--text);
  }

  .tl-header:hover {
    background: var(--surface-low);
  }

  .tl-arrow {
    font-size: 0.6rem;
    color: var(--text-muted);
    transition: transform 0.15s;
    flex-shrink: 0;
  }

  .tl-arrow.open {
    transform: rotate(90deg);
  }

  .tl-tool {
    font-weight: 600;
    font-size: 0.78rem;
    color: var(--terracotta);
    min-width: 8rem;
    flex-shrink: 0;
  }

  .tl-summary {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .tl-person {
    font-size: 0.72rem;
    color: var(--text-muted);
    text-transform: capitalize;
    flex-shrink: 0;
  }

  .tl-time {
    font-size: 0.72rem;
    color: var(--text-muted);
    flex-shrink: 0;
    white-space: nowrap;
  }

  .tl-args {
    padding: 0.5rem 0.6rem 0.75rem 2rem;
    background: var(--surface-low);
  }

  .tl-args table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.78rem;
  }

  .tl-args th {
    text-align: left;
    font-weight: 600;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-muted);
    padding: 0.2rem 0.5rem;
    border-bottom: 1px solid var(--border);
  }

  .tl-args td {
    padding: 0.25rem 0.5rem;
    vertical-align: top;
  }

  .tl-arg-key {
    font-weight: 600;
    color: var(--sage);
    white-space: nowrap;
    width: 6rem;
  }

  .tl-arg-val {
    color: var(--text);
    word-break: break-word;
  }

  .tl-total {
    font-size: 0.72rem;
    color: var(--text-muted);
    margin-top: 0.75rem;
    text-align: right;
  }
</style>

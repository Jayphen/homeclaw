<script lang="ts">
  interface SetupStatus {
    provider_configured: boolean;
    has_password: boolean;
    needs_setup_token: boolean;
    model: string;
    anthropic_api_key: string | null;
    openai_api_key: string | null;
    openai_base_url: string | null;
    telegram_configured: boolean;
    telegram_allowed_users: string | null;
    ha_configured: boolean;
  }

  import { setToken } from "$lib/api";

  let { oncomplete }: { oncomplete: () => void } = $props();

  let step: number = $state(0);
  let error: string | null = $state(null);
  let saving: boolean = $state(false);
  let status: SetupStatus | null = $state(null);

  // Form state
  let setupToken: string = $state("");
  let provider: "anthropic" | "openai" = $state("openai");
  let anthropicKey: string = $state("");
  let openaiKey: string = $state("");
  let openaiBaseUrl: string = $state("https://openrouter.ai/api/v1");
  let model: string = $state("anthropic/claude-sonnet-4-6");
  let telegramToken: string = $state("");
  let telegramAllowedUsers: string = $state("");
  let webPassword: string = $state("");
  let webPasswordConfirm: string = $state("");

  async function fetchStatus() {
    const r = await fetch("/api/setup/status");
    if (r.ok) status = await r.json();
  }

  async function submitSetup() {
    error = null;

    if (step === 0 && status?.needs_setup_token && !setupToken.trim()) {
      error = "Enter the setup token from the container logs.";
      return;
    }

    if (step === 1) {
      if (provider === "anthropic" && !anthropicKey.trim()) {
        error = "Enter your Anthropic API key.";
        return;
      }
      if (provider === "openai" && !openaiKey.trim()) {
        error = "Enter your API key.";
        return;
      }
    }

    if (step === 3) {
      if (!webPassword.trim()) {
        error = "Set a password to secure the web UI.";
        return;
      }
      if (webPassword !== webPasswordConfirm) {
        error = "Passwords don't match.";
        return;
      }
    }

    // On the last step, submit everything.
    if (step === 3) {
      saving = true;
      try {
        const body: Record<string, string | null> = {
          setup_token: setupToken || null,
          model,
          web_password: webPassword,
        };
        if (provider === "anthropic") {
          body.anthropic_api_key = anthropicKey;
        } else {
          body.openai_api_key = openaiKey;
          body.openai_base_url = openaiBaseUrl || null;
        }
        if (telegramToken.trim()) {
          body.telegram_token = telegramToken;
          if (telegramAllowedUsers.trim()) {
            body.telegram_allowed_users = telegramAllowedUsers;
          }
        }

        const r = await fetch("/api/setup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!r.ok) {
          const data = await r.json().catch(() => null);
          error = data?.detail || `Error ${r.status}`;
          saving = false;
          return;
        }
        setToken(webPassword);
        oncomplete();
      } catch (e: any) {
        error = e.message;
      }
      saving = false;
      return;
    }

    // Skip token step if not needed.
    if (step === 0 && !status?.needs_setup_token) {
      step = 1;
      return;
    }

    step++;
  }

  $effect(() => {
    fetchStatus();
  });
</script>

<div class="setup">
  <div class="setup-card">
    <h1>Welcome to homeclaw</h1>
    <p class="subtitle">Let's get your household assistant set up.</p>

    <div class="steps">
      {#each ["Token", "Provider", "Extras", "Password"] as label, i}
        <div class="step" class:active={step === i} class:done={step > i}>
          <span class="step-num">{i + 1}</span>
          <span class="step-label">{label}</span>
        </div>
      {/each}
    </div>

    {#if error}
      <div class="error">{error}</div>
    {/if}

    {#if step === 0}
      <div class="field-group">
        {#if status?.needs_setup_token}
          <label for="token">Setup token</label>
          <p class="hint">Find this in your container logs.</p>
          <input id="token" type="text" bind:value={setupToken} placeholder="Paste token here" autocomplete="off" />
        {:else}
          <p class="hint">No setup token needed — proceeding to provider setup.</p>
        {/if}
      </div>

    {:else if step === 1}
      <div class="field-group">
        <span class="field-label">LLM provider</span>
        <div class="provider-toggle">
          <button class:selected={provider === "openai"} onclick={() => { provider = "openai"; }}>
            OpenAI / OpenRouter
          </button>
          <button class:selected={provider === "anthropic"} onclick={() => { provider = "anthropic"; }}>
            Anthropic
          </button>
        </div>

        {#if provider === "anthropic"}
          <label for="anthropic-key">Anthropic API key</label>
          <input id="anthropic-key" type="password" bind:value={anthropicKey} placeholder="sk-ant-..." />
        {:else}
          <label for="openai-key">API key</label>
          <input id="openai-key" type="password" bind:value={openaiKey} placeholder="sk-..." />
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
        {/if}

        <label for="model">Model</label>
        <input id="model" type="text" bind:value={model} placeholder="anthropic/claude-sonnet-4-6" />
      </div>

    {:else if step === 2}
      <div class="field-group">
        <h2>Telegram (optional)</h2>
        <label for="tg-token">Bot token</label>
        <input id="tg-token" type="password" bind:value={telegramToken} placeholder="123456:ABC-DEF..." />
        <label for="tg-users">Allowed user IDs</label>
        <input id="tg-users" type="text" bind:value={telegramAllowedUsers} placeholder="12345678, 87654321" />
        <p class="hint">Comma-separated Telegram user IDs. Leave blank for unrestricted.</p>
        <p class="hint skip-hint">No Telegram? Just click Next.</p>
      </div>

    {:else if step === 3}
      <div class="field-group">
        <h2>Set a password</h2>
        <p class="hint">This protects the web UI and API. You'll need it to log in.</p>
        <label for="password">Password</label>
        <input id="password" type="password" bind:value={webPassword} placeholder="Choose a password" />
        <label for="password-confirm">Confirm password</label>
        <input id="password-confirm" type="password" bind:value={webPasswordConfirm} placeholder="Confirm password" />
      </div>
    {/if}

    <div class="actions">
      {#if step > 0}
        <button class="btn secondary" onclick={() => { step--; error = null; }}>Back</button>
      {/if}
      <button class="btn primary" onclick={submitSetup} disabled={saving}>
        {#if step === 3}
          {saving ? "Saving..." : "Finish setup"}
        {:else}
          Next
        {/if}
      </button>
    </div>
  </div>
</div>

<style>
  .setup {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2rem;
  }

  .setup-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 2.5rem;
    max-width: 480px;
    width: 100%;
    box-shadow: var(--shadow);
    animation: fadeUp 0.35s ease-out;
  }

  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }

  h1 {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 1.6rem;
    margin: 0 0 0.25rem;
    color: var(--text);
    letter-spacing: -0.02em;
  }

  h2 {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 1.05rem;
    margin: 0 0 0.75rem;
    color: var(--text);
  }

  .subtitle {
    color: var(--text-muted);
    font-size: 0.9rem;
    margin: 0 0 1.5rem;
  }

  /* Steps indicator */
  .steps {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1.75rem;
  }

  .step {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.3rem 0.6rem;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--text-muted);
    background: transparent;
    transition: all 0.2s;
  }

  .step.active {
    background: var(--terracotta);
    color: #fff;
  }

  .step.done {
    color: var(--sage);
  }

  .step-num {
    font-weight: 600;
    font-size: 0.7rem;
  }

  /* Fields */
  .field-group {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    min-height: 200px;
  }

  label, .field-label {
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text);
    margin-top: 0.25rem;
  }

  input {
    padding: 0.6rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: 8px;
    font-size: 0.88rem;
    font-family: var(--font-sans);
    background: #fdfcfa;
    color: var(--text);
    transition: border-color 0.15s;
  }

  input:focus {
    outline: none;
    border-color: var(--terracotta);
  }

  input::placeholder {
    color: var(--text-muted);
    opacity: 0.6;
  }

  .hint {
    font-size: 0.8rem;
    color: var(--text-muted);
    margin: 0;
    line-height: 1.4;
  }

  .skip-hint {
    margin-top: 0.5rem;
    font-style: italic;
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

  /* Provider toggle */
  .provider-toggle {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
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

  /* Error */
  .error {
    background: #fef2f0;
    border: 1px solid #f0c4bc;
    border-radius: 8px;
    padding: 0.6rem 0.85rem;
    font-size: 0.82rem;
    color: var(--terracotta);
    margin-bottom: 1rem;
  }

  /* Actions */
  .actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
    margin-top: 1.5rem;
  }

  .btn {
    padding: 0.55rem 1.25rem;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: all 0.15s;
    border: none;
  }

  .btn.primary {
    background: var(--terracotta);
    color: #fff;
  }

  .btn.primary:hover {
    filter: brightness(1.08);
  }

  .btn.primary:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .btn.secondary {
    background: transparent;
    color: var(--text-muted);
    border: 1px solid var(--border);
  }

  .btn.secondary:hover {
    color: var(--text);
    background: rgba(45, 41, 38, 0.04);
  }
</style>

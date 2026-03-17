<script lang="ts">
  import Router from "svelte-spa-router";
  import Dashboard from "./views/Dashboard.svelte";
  import Calendar from "./views/Calendar.svelte";
  import Memory from "./views/Memory.svelte";
  import Notes from "./views/Notes.svelte";
  import Contacts from "./views/Contacts.svelte";
  import Plugins from "./views/Plugins.svelte";
  import Settings from "./views/Settings.svelte";
  import Setup from "./views/Setup.svelte";
  import { api, getToken, setToken } from "$lib/api";

  const routes = {
    "/": Dashboard,
    "/calendar": Calendar,
    "/memory": Memory,
    "/notes": Notes,
    "/notes/:person": Notes,
    "/notes/:person/:date": Notes,
    "/contacts": Contacts,
    "/plugins": Plugins,
    "/settings": Settings,
  };

  type AppState = "loading" | "setup" | "login" | "ready" | "error";
  let state: AppState = $state("loading");
  let loginPassword: string = $state("");
  let loginError: string | null = $state(null);
  let loggingIn: boolean = $state(false);
  let setupError: string | null = $state(null);

  async function checkSetup() {
    try {
      const r = await fetch("/api/setup/status");
      if (!r.ok) {
        state = "error";
        setupError = `Server returned ${r.status}`;
        return;
      }
      const data = await r.json();

      if (!data.provider_configured || !data.has_password) {
        state = "setup";
        return;
      }

      // Provider + password configured. Check if we have a valid token.
      if (getToken()) {
        const check = await api("/api/settings");
        if (check.ok) {
          state = "ready";
          return;
        }
        // Token invalid/expired — fall through to login.
      }

      state = "login";
    } catch (e) {
      state = "error";
      setupError = e instanceof Error ? e.message : "Could not reach server";
    }
  }

  async function handleLogin() {
    loginError = null;
    loggingIn = true;
    setToken(loginPassword);
    try {
      const r = await api("/api/settings");
      if (r.ok) {
        state = "ready";
      } else {
        loginError = "Wrong password.";
        setToken("");
      }
    } catch {
      loginError = "Couldn't reach the server.";
      setToken("");
    }
    loggingIn = false;
  }

  function onSetupComplete() {
    state = "ready";
  }

  $effect(() => {
    checkSetup();
  });
</script>

<svelte:head>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous" />
  <link
    href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,600;1,400&family=DM+Sans:wght@400;500;600&display=swap"
    rel="stylesheet"
  />
</svelte:head>

{#if state === "loading"}
  <!-- Loading -->
{:else if state === "error"}
  <div class="login">
    <div class="login-card">
      <h1>homeclaw</h1>
      <div class="login-error">{setupError ?? "Could not connect to server"}</div>
      <button class="retry-btn" onclick={() => { state = "loading"; checkSetup(); }}>Retry</button>
    </div>
  </div>
{:else if state === "setup"}
  <Setup oncomplete={onSetupComplete} />
{:else if state === "login"}
  <div class="login">
    <div class="login-card">
      <h1>homeclaw</h1>
      {#if loginError}
        <div class="login-error">{loginError}</div>
      {/if}
      <form onsubmit={(e) => { e.preventDefault(); handleLogin(); }}>
        <label for="login-pw">Password</label>
        <input id="login-pw" type="password" bind:value={loginPassword} placeholder="Enter password" autofocus />
        <button type="submit" disabled={loggingIn}>
          {loggingIn ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </div>
  </div>
{:else}
  <nav>
    <span class="brand">homeclaw</span>
    <div class="links">
      <a href="#/">Dashboard</a>
      <a href="#/calendar">Calendar</a>
      <a href="#/notes">Notes</a>
      <a href="#/memory">Memory</a>
      <a href="#/contacts">Contacts</a>
      <a href="#/plugins">Plugins</a>
      <a href="#/settings">Settings</a>
    </div>
  </nav>

  <main>
    <Router {routes} />
  </main>
{/if}

<style>
  :global(*) {
    box-sizing: border-box;
  }

  :global(body) {
    margin: 0;
    font-family: "DM Sans", sans-serif;
    background: var(--bg);
    color: var(--text);
    -webkit-font-smoothing: antialiased;
  }

  :global(:root) {
    --bg: #faf8f4;
    --surface: #fff;
    --text: #2d2926;
    --text-muted: #8a7f78;
    --border: #e8e2da;
    --terracotta: #c4653a;
    --sage: #6b8f71;
    --amber: #d4a054;
    --rose: #b5656b;
    --font-serif: "Lora", Georgia, serif;
    --font-sans: "DM Sans", sans-serif;
    --radius: 10px;
    --shadow: 0 1px 3px rgba(45, 41, 38, 0.06), 0 4px 12px rgba(45, 41, 38, 0.04);
  }

  nav {
    display: flex;
    align-items: center;
    gap: 1.5rem;
    padding: 0.75rem 1.5rem;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
  }

  .brand {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 1.1rem;
    color: var(--terracotta);
    letter-spacing: -0.01em;
  }

  .links {
    display: flex;
    gap: 0.25rem;
  }

  .links a {
    color: var(--text-muted);
    text-decoration: none;
    font-size: 0.85rem;
    font-weight: 500;
    padding: 0.3rem 0.6rem;
    border-radius: 6px;
    transition: color 0.15s, background 0.15s;
  }

  .links a:hover {
    color: var(--text);
    background: rgba(45, 41, 38, 0.04);
  }

  main {
    max-width: 960px;
    margin: 2rem auto;
    padding: 0 1.5rem;
  }

  /* ---- Login ---- */
  .login {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2rem;
  }

  .login-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 2.5rem;
    max-width: 360px;
    width: 100%;
    box-shadow: var(--shadow);
    animation: fadeUp 0.35s ease-out;
  }

  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .login-card h1 {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 1.6rem;
    color: var(--terracotta);
    margin: 0 0 1.5rem;
    text-align: center;
    letter-spacing: -0.02em;
  }

  .login-card form {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }

  .login-card label {
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text);
  }

  .login-card input {
    padding: 0.6rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: 8px;
    font-size: 0.88rem;
    font-family: var(--font-sans);
    background: #fdfcfa;
    color: var(--text);
  }

  .login-card input:focus {
    outline: none;
    border-color: var(--terracotta);
  }

  .login-card button {
    margin-top: 0.5rem;
    padding: 0.6rem;
    border: none;
    border-radius: 8px;
    background: var(--terracotta);
    color: #fff;
    font-size: 0.85rem;
    font-weight: 600;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: filter 0.15s;
  }

  .login-card button:hover { filter: brightness(1.08); }
  .login-card button:disabled { opacity: 0.5; cursor: default; }

  .retry-btn {
    width: 100%;
    margin-top: 1rem;
    padding: 0.6rem;
    border: none;
    border-radius: 8px;
    background: var(--terracotta);
    color: #fff;
    font-size: 0.85rem;
    font-weight: 600;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: filter 0.15s;
  }

  .retry-btn:hover { filter: brightness(1.08); }

  .login-error {
    background: #fef2f0;
    border: 1px solid #f0c4bc;
    border-radius: 8px;
    padding: 0.5rem 0.75rem;
    font-size: 0.82rem;
    color: var(--terracotta);
    margin-bottom: 1rem;
    text-align: center;
  }
</style>

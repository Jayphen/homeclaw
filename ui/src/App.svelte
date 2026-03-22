<script lang="ts">
  import Router from "svelte-spa-router";
  import Bookmarks from "./views/Bookmarks.svelte";
  import Dashboard from "./views/Dashboard.svelte";
  import Calendar from "./views/Calendar.svelte";
  import Memory from "./views/Memory.svelte";
  import Notes from "./views/Notes.svelte";
  import Contacts from "./views/Contacts.svelte";
  import Plugins from "./views/Plugins.svelte";
  import Skills from "./views/Skills.svelte";
  import Settings from "./views/Settings.svelte";
  import Setup from "./views/Setup.svelte";
  import { api, getToken, setToken, clearToken } from "$lib/api";

  const routes = {
    "/": Dashboard,
    "/bookmarks": Bookmarks,
    "/calendar": Calendar,
    "/memory": Memory,
    "/notes": Notes,
    "/notes/:person": Notes,
    "/notes/:person/:date": Notes,
    "/contacts": Contacts,
    "/skills": Skills,
    "/skills/:owner/:name": Skills,
    "/skills/:owner/:name/*file": Skills,
    "/plugins": Plugins,
    "/settings": Settings,
  };

  type AppState = "loading" | "setup" | "login" | "ready" | "error";
  let state: AppState = $state("loading");
  let loginPassword: string = $state("");
  let loginMember: string = $state("");
  let loginError: string | null = $state(null);
  let loggingIn: boolean = $state(false);
  let setupError: string | null = $state(null);
  let hasMemberAccounts: boolean = $state(false);

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

      hasMemberAccounts = !!data.has_member_accounts;

      // Provider + password configured. Check if we have a valid token.
      if (getToken()) {
        const check = await api("/api/settings");
        if (check.ok) {
          state = "ready";
          return;
        }
        // Token invalid/expired — clear and fall through to login.
        clearToken();
      }

      state = "login";
    } catch (e) {
      state = "error";
      setupError = e instanceof Error ? e.message : "Could not reach server";
    }
  }

  async function handleLogin() {
    loginError = null;
    if (!loginMember.trim()) {
      loginError = "Please enter your name.";
      return;
    }
    loggingIn = true;
    try {
      const body = { member: loginMember.trim(), password: loginPassword };
      const r = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (r.ok) {
        const data = await r.json();
        setToken(data.token);
        state = "ready";
      } else {
        loginError = "Wrong password.";
      }
    } catch {
      loginError = "Couldn't reach the server.";
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
    href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400&family=Plus+Jakarta+Sans:wght@400;500;600&display=swap"
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
        <label for="login-member">Name</label>
        <input id="login-member" type="text" bind:value={loginMember} placeholder="Your name" autofocus />
        <label for="login-pw">Password</label>
        <input id="login-pw" type="password" bind:value={loginPassword} placeholder="Enter password" />
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
      <a href="#/bookmarks">Bookmarks</a>
      <a href="#/calendar">Calendar</a>
      <a href="#/notes">Notes</a>
      <a href="#/memory">Memory</a>
      <a href="#/contacts">Contacts</a>
      <a href="#/skills">Skills</a>
      <a href="#/plugins">Plugins</a>
      <a href="#/settings">Settings</a>
      <button class="sign-out" onclick={() => { clearToken(); state = "login"; }}>Sign out</button>
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
    font-family: "Plus Jakarta Sans", sans-serif;
    background: var(--bg);
    color: var(--text);
    -webkit-font-smoothing: antialiased;
  }

  :global(:root) {
    --bg: #fcf9f1;
    --surface: #ffffff;
    --surface-low: #f6f3eb;
    --surface-bright: rgba(255, 255, 255, 0.72);
    --text: #1c1c17;
    --text-muted: #78766d;
    --border: rgba(198, 200, 184, 0.2);
    --border-focus: #56642b;
    --primary: #56642b;
    --primary-container: #8a9a5b;
    --secondary: #c4653a;
    --on-primary: #ffffff;
    --on-secondary: #ffffff;
    --terracotta: #c4653a;
    --sage: #56642b;
    --amber: #d4a054;
    --rose: #b5656b;
    --font-serif: "Newsreader", Georgia, serif;
    --font-sans: "Plus Jakarta Sans", sans-serif;
    --radius: 2rem;
    --radius-md: 1.5rem;
    --radius-sm: 0.5rem;
    --radius-pill: 3rem;
    --shadow: 0 0 40px -10px rgba(28, 28, 23, 0.06);
  }

  nav {
    display: flex;
    align-items: center;
    gap: 1.5rem;
    padding: 0.75rem 1.5rem;
    background: var(--surface-bright);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    position: sticky;
    top: 0;
    z-index: 100;
  }

  .brand {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 1.1rem;
    color: var(--secondary);
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
    border-radius: var(--radius-sm);
    transition: color 0.15s, background 0.15s;
  }

  .links a:hover {
    color: var(--text);
    background: var(--surface-low);
  }

  .sign-out {
    color: var(--text-muted);
    font-size: 0.85rem;
    font-weight: 500;
    padding: 0.3rem 0.6rem;
    border-radius: var(--radius-sm);
    border: none;
    background: none;
    cursor: pointer;
    font-family: var(--font-sans);
    transition: color 0.15s, background 0.15s;
  }

  .sign-out:hover {
    color: var(--text);
    background: var(--surface-low);
  }

  main {
    max-width: 960px;
    margin: 2.75rem auto;
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
    color: var(--secondary);
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
    border-radius: var(--radius-md);
    font-size: 0.88rem;
    font-family: var(--font-sans);
    background: var(--surface-low);
    color: var(--text);
  }

  .login-card input:focus {
    outline: none;
    border-color: var(--primary);
  }

  .login-card button {
    margin-top: 0.5rem;
    padding: 0.6rem;
    border: none;
    border-radius: var(--radius-pill);
    background: linear-gradient(135deg, var(--primary), var(--primary-container));
    color: var(--on-primary);
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
    border-radius: var(--radius-pill);
    background: linear-gradient(135deg, var(--primary), var(--primary-container));
    color: var(--on-primary);
    font-size: 0.85rem;
    font-weight: 600;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: filter 0.15s;
  }

  .retry-btn:hover { filter: brightness(1.08); }

  .login-error {
    background: #fef2f0;
    border-radius: var(--radius-sm);
    padding: 0.5rem 0.75rem;
    font-size: 0.82rem;
    color: var(--secondary);
    margin-bottom: 1rem;
    text-align: center;
  }
</style>

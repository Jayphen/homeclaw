<script lang="ts">
  import Router from "svelte-spa-router";
  import Bookmarks from "./views/Bookmarks.svelte";
  import Dashboard from "./views/Dashboard.svelte";
  import Calendar from "./views/Calendar.svelte";
  import Knowledge from "./views/Knowledge.svelte";
  import Contacts from "./views/Contacts.svelte";
  import Skills from "./views/Skills.svelte";
  import Routines from "./views/Routines.svelte";
  import Settings from "./views/Settings.svelte";
  import Setup from "./views/Setup.svelte";
  import { api, getToken, setToken, clearToken } from "$lib/api";

  const routes = {
    "/": Dashboard,
    "/bookmarks": Bookmarks,
    "/calendar": Calendar,
    "/knowledge": Knowledge,
    "/knowledge/:person/:date": Knowledge,
    "/notes": Knowledge,
    "/notes/:person/:date": Knowledge,
    "/contacts": Contacts,
    "/contacts/:id": Contacts,
    "/routines": Routines,
    "/skills": Skills,
    "/skills/:owner/:name": Skills,
    "/skills/:owner/:name/*file": Skills,
    "/plugins": Skills,
    "/extensions": Skills,
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
  <div class="shell">
    <aside class="sidebar">
      <a href="#/" class="brand">homeclaw</a>

      <nav class="nav-group">
        <a href="#/">Home</a>
        <a href="#/knowledge">Knowledge</a>
        <a href="#/calendar">Calendar</a>
        <a href="#/bookmarks">Bookmarks</a>
        <a href="#/contacts">Contacts</a>
        <a href="#/routines">Routines</a>
      </nav>

      <nav class="nav-group">
        <span class="nav-label">Extend</span>
        <a href="#/skills">Extensions</a>
      </nav>

      <div class="sidebar-spacer"></div>

      <nav class="nav-group nav-bottom">
        <a href="#/settings">Settings</a>
        <button class="sign-out" onclick={() => { clearToken(); state = "login"; }}>
          Sign out
        </button>
      </nav>
    </aside>

    <main>
      <Router {routes} />
    </main>
  </div>

  <!-- Mobile bottom bar -->
  <nav class="mobile-bar">
    <a href="#/">Home</a>
    <a href="#/knowledge">Knowledge</a>
    <a href="#/contacts">Contacts</a>
    <a href="#/settings">Settings</a>
  </nav>
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

  /* ---- Shell layout ---- */
  .shell {
    display: flex;
    min-height: 100vh;
  }

  /* ---- Sidebar ---- */
  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    width: 200px;
    height: 100vh;
    display: flex;
    flex-direction: column;
    padding: 1.5rem 1rem;
    background: var(--surface-low);
    z-index: 100;
    overflow-y: auto;
  }

  .brand {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 1.15rem;
    color: var(--secondary);
    letter-spacing: -0.02em;
    text-decoration: none;
    padding: 0 0.5rem;
    margin-bottom: 1.75rem;
  }

  .nav-group {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
    margin-bottom: 1.25rem;
  }

  .nav-label {
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    padding: 0 0.5rem;
    margin-bottom: 0.3rem;
  }

  .nav-group a {
    color: var(--text-muted);
    text-decoration: none;
    font-size: 0.85rem;
    font-weight: 500;
    padding: 0.4rem 0.5rem;
    border-radius: var(--radius-sm);
    transition: color 0.15s, background 0.15s;
  }

  .nav-group a:hover {
    color: var(--text);
    background: var(--surface-low);
  }

  .sidebar-spacer {
    flex: 1;
  }

  .nav-bottom {
    margin-bottom: 0;
  }

  .sign-out {
    color: var(--text-muted);
    font-size: 0.85rem;
    font-weight: 500;
    padding: 0.4rem 0.5rem;
    border-radius: var(--radius-sm);
    border: none;
    background: none;
    cursor: pointer;
    font-family: var(--font-sans);
    text-align: left;
    transition: color 0.15s, background 0.15s;
  }

  .sign-out:hover {
    color: var(--text);
    background: var(--surface-low);
  }

  main {
    flex: 1;
    max-width: 960px;
    margin: 2.75rem auto;
    padding: 0 1.5rem;
    margin-left: calc(200px + max((100vw - 200px - 960px) / 2, 1.5rem));
  }

  /* ---- Mobile bottom bar ---- */
  .mobile-bar {
    display: none;
  }

  @media (max-width: 768px) {
    .sidebar {
      display: none;
    }

    main {
      margin-left: auto;
      margin-bottom: 4rem;
    }

    .mobile-bar {
      display: flex;
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      background: var(--surface-bright);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      padding: 0.5rem 0.75rem;
      justify-content: space-around;
      z-index: 100;
    }

    .mobile-bar a {
      color: var(--text-muted);
      text-decoration: none;
      font-size: 0.75rem;
      font-weight: 500;
      padding: 0.35rem 0.5rem;
      border-radius: var(--radius-sm);
      transition: color 0.15s;
    }

    .mobile-bar a:hover {
      color: var(--text);
    }
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

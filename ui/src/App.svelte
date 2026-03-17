<script lang="ts">
  import Router from "svelte-spa-router";
  import Dashboard from "./views/Dashboard.svelte";
  import Calendar from "./views/Calendar.svelte";
  import Memory from "./views/Memory.svelte";
  import Notes from "./views/Notes.svelte";
  import Contacts from "./views/Contacts.svelte";
  import Plugins from "./views/Plugins.svelte";

  const routes = {
    "/": Dashboard,
    "/calendar": Calendar,
    "/memory": Memory,
    "/notes": Notes,
    "/notes/:person": Notes,
    "/notes/:person/:date": Notes,
    "/contacts": Contacts,
    "/plugins": Plugins,
  };
</script>

<svelte:head>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous" />
  <link
    href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,600;1,400&family=DM+Sans:wght@400;500;600&display=swap"
    rel="stylesheet"
  />
</svelte:head>

<nav>
  <span class="brand">homeclaw</span>
  <div class="links">
    <a href="#/">Dashboard</a>
    <a href="#/calendar">Calendar</a>
    <a href="#/notes">Notes</a>
    <a href="#/memory">Memory</a>
    <a href="#/contacts">Contacts</a>
    <a href="#/plugins">Plugins</a>
  </div>
</nav>

<main>
  <Router {routes} />
</main>

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
</style>

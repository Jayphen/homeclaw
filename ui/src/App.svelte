<script lang="ts">
  import Router from "svelte-spa-router";
  import Dashboard from "./views/Dashboard.svelte";
  import Calendar from "./views/Calendar.svelte";
  import Memory from "./views/Memory.svelte";
  import Contacts from "./views/Contacts.svelte";
  import Plugins from "./views/Plugins.svelte";

  const routes = {
    "/": Dashboard,
    "/calendar": Calendar,
    "/memory": Memory,
    "/contacts": Contacts,
    "/plugins": Plugins,
  };
</script>

<nav>
  <a href="#/">Dashboard</a>
  <a href="#/calendar">Calendar</a>
  <a href="#/memory">Memory</a>
  <a href="#/contacts">Contacts</a>
  <a href="#/plugins">Plugins</a>
</nav>

<main>
  <Router {routes} />
</main>

<style>
  :global(body) {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
      sans-serif;
    background: #f8f9fa;
    color: #1a1a1a;
  }

  nav {
    display: flex;
    gap: 1rem;
    padding: 0.75rem 1.5rem;
    background: #fff;
    border-bottom: 1px solid #e0e0e0;
  }

  nav a {
    color: #555;
    text-decoration: none;
    font-size: 0.9rem;
    font-weight: 500;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
  }

  nav a:hover {
    color: #1a1a1a;
    background: #f0f0f0;
  }

  main {
    max-width: 960px;
    margin: 2rem auto;
    padding: 0 1.5rem;
  }
</style>

<script>
  import '../app.css';
  import Header from '$lib/Header.svelte';
  import Sidebar from '$lib/Sidebar.svelte';

  let { children } = $props();
  let sidebarOpen = $state(false);
</script>

<Header onMenuToggle={() => (sidebarOpen = !sidebarOpen)} />
<Sidebar bind:open={sidebarOpen} />

<main>
  <article>
    {@render children()}
  </article>
</main>

<style>
  main {
    margin-top: var(--header-height);
    margin-left: var(--sidebar-width);
    padding: 2.5rem 2rem;
  }

  article {
    max-width: var(--content-max-width);
    margin: 0 auto;
  }

  /* Markdown content styles */
  article :global(h1) {
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    margin-bottom: 0.5rem;
    color: var(--text);
  }

  article :global(h2) {
    font-size: 1.4rem;
    font-weight: 600;
    margin-top: 2.5rem;
    margin-bottom: 0.75rem;
    padding-bottom: 0.35rem;
    border-bottom: 1px solid var(--border-light);
  }

  article :global(h3) {
    font-size: 1.15rem;
    font-weight: 600;
    margin-top: 1.75rem;
    margin-bottom: 0.5rem;
  }

  article :global(p) {
    margin-bottom: 1rem;
  }

  article :global(ul),
  article :global(ol) {
    margin-bottom: 1rem;
    padding-left: 1.5rem;
  }

  article :global(li) {
    margin-bottom: 0.35rem;
  }

  article :global(table) {
    width: 100%;
    border-collapse: collapse;
    margin: 1.25rem 0;
    font-size: 0.9rem;
  }

  article :global(th),
  article :global(td) {
    padding: 0.6rem 0.75rem;
    border: 1px solid var(--border);
    text-align: left;
  }

  article :global(th) {
    background: var(--bg-alt);
    font-weight: 600;
  }

  article :global(blockquote) {
    border-left: 3px solid var(--terracotta-light);
    padding: 0.5rem 1rem;
    margin: 1.25rem 0;
    color: var(--text-muted);
    background: var(--bg-alt);
    border-radius: 0 6px 6px 0;
  }

  article :global(.lead) {
    font-size: 1.15rem;
    color: var(--text-muted);
    margin-bottom: 2rem;
  }

  @media (max-width: 768px) {
    main {
      margin-left: 0;
      padding: 1.5rem 1rem;
    }
  }
</style>

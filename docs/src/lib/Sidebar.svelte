<script>
  import { page } from '$app/stores';
  import { nav } from './nav.js';

  let { open = $bindable(false) } = $props();
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
{#if open}
  <div class="overlay" onclick={() => (open = false)}></div>
{/if}

<aside class:open>
  <nav>
    {#each nav as section}
      <div class="section">
        <h3>{section.title}</h3>
        <ul>
          {#each section.items as item}
            <li>
              <a
                href={item.href}
                class:active={$page.url.pathname === item.href}
                onclick={() => (open = false)}
              >
                {item.title}
              </a>
            </li>
          {/each}
        </ul>
      </div>
    {/each}
  </nav>
</aside>

<style>
  .overlay {
    display: none;
  }

  aside {
    position: fixed;
    top: var(--header-height);
    left: 0;
    bottom: 0;
    width: var(--sidebar-width);
    overflow-y: auto;
    padding: 1.5rem 1rem;
    border-right: 1px solid var(--border);
    background: var(--surface);
    z-index: 10;
  }

  .section {
    margin-bottom: 1.5rem;
  }

  h3 {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    margin-bottom: 0.5rem;
    padding: 0 0.75rem;
  }

  ul {
    list-style: none;
    padding: 0;
  }

  li a {
    display: block;
    padding: 0.35rem 0.75rem;
    border-radius: 6px;
    font-size: 0.9rem;
    color: var(--text);
    transition: background 0.15s;
  }

  li a:hover {
    background: var(--bg-alt);
    text-decoration: none;
  }

  li a.active {
    background: var(--bg-alt);
    color: var(--terracotta);
    font-weight: 500;
  }

  @media (max-width: 768px) {
    .overlay {
      display: block;
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.3);
      z-index: 9;
    }

    aside {
      transform: translateX(-100%);
      transition: transform 0.2s ease;
    }

    aside.open {
      transform: translateX(0);
    }
  }
</style>

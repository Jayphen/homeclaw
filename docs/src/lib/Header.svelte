<script>
  let { onMenuToggle } = $props();
</script>

<header>
  <div class="left">
    <button class="menu-btn" onclick={onMenuToggle} aria-label="Toggle menu">
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
      </svg>
    </button>
    <a href="/" class="logo">
      <span class="logo-text">homeclaw</span>
      <span class="badge">docs</span>
      <span class="version">v{__HOMECLAW_VERSION__}</span>
    </a>
  </div>
  <div class="right">
    <a href="https://github.com/Jayphen/homeclaw" class="gh-link" target="_blank" rel="noopener">
      GitHub
    </a>
  </div>
</header>

<style>
  header {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: var(--header-height);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 1.25rem;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    z-index: 20;
  }

  .left {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .menu-btn {
    display: none;
    background: none;
    border: none;
    cursor: pointer;
    padding: 4px;
    color: var(--text);
  }

  .logo {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: var(--text);
  }

  .logo:hover {
    text-decoration: none;
  }

  .logo-text {
    font-size: 1.1rem;
    font-weight: 700;
    letter-spacing: -0.02em;
  }

  .badge {
    font-size: 0.7rem;
    font-weight: 500;
    padding: 0.15em 0.45em;
    background: var(--terracotta);
    color: white;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .version {
    font-size: 0.75rem;
    color: var(--text-light);
    font-weight: 400;
  }

  .right {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .gh-link {
    font-size: 0.875rem;
    color: var(--text-muted);
  }

  .gh-link:hover {
    color: var(--text);
  }

  @media (max-width: 768px) {
    .menu-btn {
      display: block;
    }
  }
</style>

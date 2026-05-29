<script lang="ts">
  import { api } from "$lib/api";

  interface SkillUiApp {
    entry: string;
    title: string | null;
  }

  interface SkillEntry {
    name: string;
    owner: string;
    description: string;
    ui_app?: SkillUiApp | null;
  }

  let apps: SkillEntry[] = $state([]);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);

  async function fetchApps() {
    loading = true;
    error = null;
    try {
      const r = await api("/api/skills");
      if (!r.ok) throw new Error(`${r.status}`);
      const data = await r.json();
      const skills: SkillEntry[] = data.skills ?? [];
      apps = skills.filter((s) => s.ui_app);
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    fetchApps();
  });
</script>

<div class="apps-page">
  <h1 class="page-title">Apps</h1>

  {#if loading}
    <div class="loading">
      <div class="loading-dot"></div>
      <div class="loading-dot"></div>
      <div class="loading-dot"></div>
    </div>
  {:else if error}
    <div class="error-card">Couldn't load apps: {error}</div>
  {:else if apps.length === 0}
    <div class="empty">
      <p>No mini-apps yet.</p>
      <p class="empty-hint">
        Mini-apps come from skills with an embedded UI. Install or create one from
        <a href="#/skills">Skills</a>.
      </p>
    </div>
  {:else}
    <div class="app-grid">
      {#each apps as app (app.owner + "/" + app.name)}
        <a class="app-card" href="#/apps/{app.owner}/{app.name}">
          <div class="app-card-top">
            <span class="app-icon">🧩</span>
            <span class="owner-tag">{app.owner}</span>
          </div>
          <h2 class="app-name">{app.ui_app?.title || app.name}</h2>
          {#if app.description}
            <p class="app-desc">{app.description}</p>
          {/if}
        </a>
      {/each}
    </div>
  {/if}
</div>

<style>
  .page-title {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 1.75rem;
    color: var(--text);
    letter-spacing: -0.02em;
    margin: 0 0 1.5rem;
  }

  .app-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 1rem;
  }

  .app-card {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 1.25rem;
    text-decoration: none;
    color: var(--text);
    box-shadow: var(--shadow);
    transition: transform 0.15s, border-color 0.15s;
  }

  .app-card:hover {
    transform: translateY(-2px);
    border-color: var(--border-focus);
  }

  .app-card-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .app-icon {
    font-size: 1.4rem;
  }

  .owner-tag {
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-muted);
    background: var(--surface-low);
    padding: 0.15rem 0.5rem;
    border-radius: var(--radius-pill);
  }

  .app-name {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 1.1rem;
    margin: 0;
    letter-spacing: -0.01em;
  }

  .app-desc {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin: 0;
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .empty {
    text-align: center;
    color: var(--text-muted);
    padding: 3rem 1rem;
  }

  .empty-hint {
    font-size: 0.88rem;
  }

  .empty a {
    color: var(--primary);
  }

  .error-card {
    background: #fef2f0;
    border-radius: var(--radius-sm);
    padding: 0.75rem 1rem;
    font-size: 0.85rem;
    color: var(--secondary);
  }

  .loading {
    display: flex;
    gap: 0.4rem;
    justify-content: center;
    padding: 3rem;
  }

  .loading-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--primary-container);
    animation: pulse 1.2s ease-in-out infinite;
  }

  .loading-dot:nth-child(2) {
    animation-delay: 0.2s;
  }

  .loading-dot:nth-child(3) {
    animation-delay: 0.4s;
  }

  @keyframes pulse {
    0%,
    100% {
      opacity: 0.3;
      transform: scale(0.8);
    }
    50% {
      opacity: 1;
      transform: scale(1);
    }
  }
</style>

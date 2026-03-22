<script lang="ts">
  import { api } from "$lib/api";
  import { renderMarkdown } from "$lib/markdown";

  interface Bookmark {
    id: string;
    url: string | null;
    title: string;
    category: string;
    tags: string[];
    saved_by: string;
    saved_at: string | null;
    notes_md: string | null;
  }

  let bookmarks: Bookmark[] = $state([]);
  let categories: string[] = $state([]);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);
  let search: string = $state("");
  let activeCategory: string | null = $state(null);

  const filtered = $derived.by(() => {
    if (!search.trim() && !activeCategory) return bookmarks;
    let results = bookmarks;
    if (activeCategory) {
      results = results.filter((b) => b.category === activeCategory);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      results = results.filter(
        (b) =>
          b.title.toLowerCase().includes(q) ||
          b.tags.some((t) => t.toLowerCase().includes(q)),
      );
    }
    return results;
  });

  function formatDate(iso: string): string {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }

  async function fetchBookmarks() {
    loading = true;
    error = null;
    try {
      const r = await api("/api/bookmarks");
      if (!r.ok) throw new Error(`${r.status}`);
      const data = await r.json();
      bookmarks = data.bookmarks;
      categories = data.categories;
    } catch (e: any) {
      error = e.message;
    }
    loading = false;
  }

  function selectCategory(cat: string) {
    activeCategory = activeCategory === cat ? null : cat;
  }

  async function deleteBookmark(id: string) {
    try {
      const r = await api(`/api/bookmarks/${id}`, { method: "DELETE" });
      if (!r.ok) throw new Error(`${r.status}`);
      bookmarks = bookmarks.filter((b) => b.id !== id);
    } catch (e: any) {
      error = e.message;
    }
  }

  $effect(() => {
    fetchBookmarks();
  });
</script>

{#if loading}
  <div class="loading">
    <div class="loading-dot"></div>
    <div class="loading-dot"></div>
    <div class="loading-dot"></div>
  </div>
{:else if error}
  <div class="error-card">
    <p>Couldn't load bookmarks</p>
    <small>{error}</small>
  </div>
{:else}
  <header class="page-header">
    <h1>Bookmarks</h1>
    <p class="subtitle">
      {bookmarks.length} saved {bookmarks.length === 1 ? "item" : "items"}
    </p>
  </header>

  <div class="search-bar">
    <input
      type="text"
      placeholder="Search bookmarks..."
      bind:value={search}
    />
  </div>

  {#if categories.length > 0}
    <div class="category-bar">
      {#each categories as cat}
        <button
          class="category-chip"
          class:active={activeCategory === cat}
          onclick={() => selectCategory(cat)}
        >
          {cat}
        </button>
      {/each}
    </div>
  {/if}

  {#if filtered.length === 0}
    <div class="empty">
      {#if search.trim() || activeCategory}
        <p>No bookmarks match your filter</p>
      {:else}
        <p>No bookmarks yet</p>
        <small>Share links and places with homeclaw to start saving them.</small>
      {/if}
    </div>
  {:else}
    <div class="bookmark-list">
      {#each filtered as bm, i}
        <div class="bookmark-card">
          <div class="bm-main">
            <div class="bm-title-row">
              {#if bm.url}
                <a class="bm-title" href={bm.url} target="_blank" rel="noopener">
                  {bm.title}
                </a>
              {:else}
                <span class="bm-title">{bm.title}</span>
              {/if}
              <button
                class="bm-delete"
                onclick={() => deleteBookmark(bm.id)}
                title="Delete bookmark"
              >&times;</button>
            </div>

            {#if bm.notes_md}
              <div class="bm-notes">{@html renderMarkdown(bm.notes_md)}</div>
            {/if}

            <div class="bm-meta">
              <span class="badge cat-badge">{bm.category}</span>
              {#each bm.tags as tag}
                <span class="badge tag-badge">{tag}</span>
              {/each}
              {#if bm.saved_by}
                <span class="bm-saved-by">by {bm.saved_by}</span>
              {/if}
              {#if bm.saved_at}
                <span class="bm-date">{formatDate(bm.saved_at)}</span>
              {/if}
            </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}
{/if}

<style>
  /* ---- Loading ---- */
  .loading {
    display: flex;
    justify-content: center;
    gap: 0.5rem;
    padding: 4rem 0;
  }

  .loading-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--primary);
    opacity: 0.3;
    animation: pulse 1s ease-in-out infinite;
  }

  .loading-dot:nth-child(2) { animation-delay: 0.15s; }
  .loading-dot:nth-child(3) { animation-delay: 0.3s; }

  @keyframes pulse {
    0%, 100% { opacity: 0.3; transform: scale(1); }
    50% { opacity: 1; transform: scale(1.2); }
  }

  /* ---- Error ---- */
  .error-card {
    background: #fef2f0;
    border-radius: var(--radius);
    padding: 1.5rem;
    text-align: center;
    color: var(--secondary);
  }

  .error-card p { margin: 0 0 0.5rem; font-weight: 500; }
  .error-card small { color: var(--text-muted); }

  /* ---- Header ---- */
  .page-header { margin-bottom: 1.5rem; }

  .page-header h1 {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 2rem;
    margin: 0;
    color: var(--text);
    letter-spacing: -0.02em;
  }

  .subtitle {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin: 0.25rem 0 0;
  }

  /* ---- Search ---- */
  .search-bar { margin-bottom: 1rem; }

  .search-bar input {
    width: 100%;
    padding: 0.6rem 0.9rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    background: var(--surface-low);
    font-family: var(--font-sans);
    font-size: 0.88rem;
    color: var(--text);
    outline: none;
    transition: border-color 0.15s;
    box-sizing: border-box;
  }

  .search-bar input:focus { border-color: var(--primary); }
  .search-bar input::placeholder { color: var(--text-muted); }

  /* ---- Category chips ---- */
  .category-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-bottom: 1.25rem;
  }

  .category-chip {
    padding: 0.3rem 0.7rem;
    border: none;
    border-radius: var(--radius-pill);
    background: var(--surface);
    color: var(--text-muted);
    font-family: var(--font-sans);
    font-size: 0.78rem;
    font-weight: 500;
    cursor: pointer;
    transition: color 0.15s, background 0.15s, box-shadow 0.15s;
    text-transform: capitalize;
  }

  .category-chip:hover {
    background: var(--surface-low);
    color: var(--text);
  }

  .category-chip.active {
    background: var(--surface-low);
    color: var(--primary);
    box-shadow: inset 0 0 0 1px rgba(198, 200, 184, 0.2);
  }

  /* ---- Bookmark list ---- */
  .bookmark-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .bookmark-card {
    background: var(--surface);
    border-radius: var(--radius);
    padding: 0.85rem 1.1rem;
    transition: box-shadow 0.15s, background 0.15s;
  }

  .bookmark-card:hover {
    box-shadow: inset 0 0 0 1px var(--border);
    background: var(--surface-low);
  }

  .bm-main {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }

  .bm-title-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .bm-title {
    font-weight: 600;
    font-size: 0.92rem;
    color: var(--text);
    text-decoration: none;
  }

  a.bm-title:hover {
    color: var(--primary);
  }

  .bm-delete {
    flex-shrink: 0;
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 1.1rem;
    cursor: pointer;
    padding: 0 0.2rem;
    line-height: 1;
    border-radius: var(--radius-sm);
    opacity: 0;
    transition: opacity 0.15s, color 0.15s;
  }

  .bookmark-card:hover .bm-delete { opacity: 1; }
  .bm-delete:hover { color: var(--primary); }

  .bm-notes {
    font-family: var(--font-sans);
    font-size: 0.82rem;
    line-height: 1.5;
    color: var(--text-muted);
    margin: 0.25rem 0 0;
    padding: 0.5rem 0.75rem;
    background: var(--surface-low);
    border-radius: var(--radius-sm);
  }

  .bm-notes :global(p) { margin: 0 0 0.3rem; }
  .bm-notes :global(p:last-child) { margin-bottom: 0; }
  .bm-notes :global(ul), .bm-notes :global(ol) { margin: 0.2rem 0; padding-left: 1.2rem; }

  .bm-meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.35rem;
    margin-top: 0.3rem;
  }

  /* ---- Badges ---- */
  .badge {
    display: inline-block;
    font-size: 0.68rem;
    font-weight: 600;
    padding: 0.1rem 0.4rem;
    border-radius: var(--radius-sm);
    letter-spacing: 0.02em;
    text-transform: capitalize;
  }

  .cat-badge {
    background: var(--surface-low);
    color: var(--text-muted);
  }

  .tag-badge {
    background: #eef4ef;
    color: var(--sage);
  }

  .bm-saved-by, .bm-date {
    font-size: 0.72rem;
    color: var(--text-muted);
  }

  /* ---- Empty ---- */
  .empty {
    text-align: center;
    padding: 3rem 1rem;
    color: var(--text-muted);
  }

  .empty p {
    font-family: var(--font-serif);
    font-style: italic;
    font-size: 1.1rem;
    margin: 0 0 0.5rem;
  }

  .empty small { font-size: 0.82rem; }
</style>

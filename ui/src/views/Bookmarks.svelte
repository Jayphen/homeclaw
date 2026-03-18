<script lang="ts">
  import { api } from "$lib/api";

  interface Bookmark {
    id: string;
    url: string | null;
    title: string;
    category: string;
    tags: string[];
    saved_by: string;
    saved_at: string | null;
    neighborhood: string;
    city: string;
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
          b.tags.some((t) => t.toLowerCase().includes(q)) ||
          b.neighborhood.toLowerCase().includes(q) ||
          b.city.toLowerCase().includes(q),
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
  <header class="page-header" style="animation-delay: 0ms">
    <h1>Bookmarks</h1>
    <p class="subtitle">
      {bookmarks.length} saved {bookmarks.length === 1 ? "item" : "items"}
    </p>
  </header>

  <div class="search-bar" style="animation-delay: 60ms">
    <input
      type="text"
      placeholder="Search bookmarks..."
      bind:value={search}
    />
  </div>

  {#if categories.length > 0}
    <div class="category-bar" style="animation-delay: 90ms">
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
    <div class="empty" style="animation-delay: 120ms">
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
        <div class="bookmark-card" style="animation-delay: {120 + i * 30}ms">
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

            {#if bm.neighborhood || bm.city}
              <span class="bm-location">
                {[bm.neighborhood, bm.city].filter(Boolean).join(", ")}
              </span>
            {/if}

            {#if bm.notes_md}
              <pre class="bm-notes">{bm.notes_md}</pre>
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
  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(12px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .page-header, .search-bar, .category-bar, .bookmark-card, .empty {
    opacity: 0;
    animation: fadeUp 0.4s ease-out forwards;
  }

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
    background: var(--terracotta);
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
    border: 1px solid #f0c4bc;
    border-radius: var(--radius);
    padding: 1.5rem;
    text-align: center;
    color: var(--terracotta);
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
    border-radius: var(--radius);
    background: var(--surface);
    font-family: var(--font-sans);
    font-size: 0.88rem;
    color: var(--text);
    outline: none;
    transition: border-color 0.15s;
    box-sizing: border-box;
  }

  .search-bar input:focus { border-color: var(--terracotta); }
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
    border: 1px solid var(--border);
    border-radius: 20px;
    background: var(--surface);
    color: var(--text-muted);
    font-family: var(--font-sans);
    font-size: 0.78rem;
    font-weight: 500;
    cursor: pointer;
    transition: border-color 0.15s, color 0.15s, background 0.15s;
    text-transform: capitalize;
  }

  .category-chip:hover {
    border-color: #d0c8be;
    color: var(--text);
  }

  .category-chip.active {
    border-color: var(--terracotta);
    background: #fef9f4;
    color: var(--terracotta);
  }

  /* ---- Bookmark list ---- */
  .bookmark-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .bookmark-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.85rem 1.1rem;
    transition: border-color 0.15s;
  }

  .bookmark-card:hover {
    border-color: #d0c8be;
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
    color: var(--terracotta);
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
    border-radius: 4px;
    opacity: 0;
    transition: opacity 0.15s, color 0.15s;
  }

  .bookmark-card:hover .bm-delete { opacity: 1; }
  .bm-delete:hover { color: var(--terracotta); }

  .bm-location {
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .bm-notes {
    font-family: var(--font-sans);
    font-size: 0.82rem;
    line-height: 1.5;
    color: var(--text-muted);
    margin: 0.25rem 0 0;
    padding: 0.5rem 0.75rem;
    background: #fdfcfa;
    border-left: 3px solid var(--sage);
    border-radius: 4px;
    white-space: pre-wrap;
    word-wrap: break-word;
  }

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
    border-radius: 4px;
    letter-spacing: 0.02em;
    text-transform: capitalize;
  }

  .cat-badge {
    background: #f0ebe5;
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

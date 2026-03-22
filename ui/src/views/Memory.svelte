<script lang="ts">
  import { api } from "$lib/api";

  interface MemberSummary {
    person: string;
    topic_count: number;
    topics: string[];
    last_updated: string | null;
  }

  interface RecallResult {
    person: string;
    query: string;
    results: Array<{ text: string; score: number }>;
    note?: string;
  }

  let members: MemberSummary[] = $state([]);
  let semanticReady: boolean = $state(false);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);

  let selectedPerson: string | null = $state(null);
  let topicContents: Record<string, string> | null = $state(null);
  let detailLoading: boolean = $state(false);

  let searchQuery: string = $state("");
  let searchResults: RecallResult | null = $state(null);
  let searching: boolean = $state(false);

  function formatUpdated(iso: string | null): string {
    if (!iso) return "never";
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffHours = Math.floor(diffMs / 3600000);
    if (diffHours < 1) return "just now";
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays === 1) return "yesterday";
    if (diffDays < 30) return `${diffDays} days ago`;
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  }

  async function fetchMembers() {
    loading = true;
    error = null;
    try {
      const r = await api("/api/memory");
      if (!r.ok) throw new Error(`${r.status}`);
      const data = await r.json();
      members = data.members;
      semanticReady = data.semantic_ready;
      loading = false;
    } catch (e: any) {
      error = e.message;
      loading = false;
    }
  }

  async function selectPerson(person: string) {
    if (selectedPerson === person) {
      selectedPerson = null;
      topicContents = null;
      searchResults = null;
      return;
    }
    selectedPerson = person;
    detailLoading = true;
    searchResults = null;
    searchQuery = "";
    try {
      const r = await api(`/api/memory/${person}`);
      if (!r.ok) throw new Error(`${r.status}`);
      const data = await r.json();
      topicContents = data.topics;
      detailLoading = false;
    } catch (e: any) {
      error = e.message;
      detailLoading = false;
    }
  }

  async function doSearch() {
    if (!selectedPerson || !searchQuery.trim()) return;
    searching = true;
    try {
      const r = await api(
        `/api/memory/${selectedPerson}/recall?q=${encodeURIComponent(searchQuery.trim())}`,
      );
      if (!r.ok) throw new Error(`${r.status}`);
      searchResults = await r.json();
    } catch (e: any) {
      error = e.message;
    }
    searching = false;
  }

  $effect(() => {
    fetchMembers();
  });
</script>

<div class="memory-page">
  <header class="mem-header">
    <h1>Memory</h1>
  </header>

  {#if loading}
    <div class="loading">
      <div class="loading-dot"></div>
      <div class="loading-dot"></div>
      <div class="loading-dot"></div>
    </div>
  {:else if error}
    <div class="error-card">
      <p>Couldn't load memory.</p>
      <small>{error}</small>
    </div>
  {:else}
    <div class="member-list">
      {#each members as member, i}
        {@const isActive = selectedPerson === member.person}
        <button
          class="member-card"
          class:active={isActive}
          onclick={() => selectPerson(member.person)}
          style="animation-delay: {i * 50}ms"
        >
          <div class="member-info">
            <span class="member-name">{member.person}</span>
            <span class="member-stats">
              {member.topic_count} {member.topic_count === 1 ? "topic" : "topics"}
            </span>
          </div>
          <span class="member-updated">
            {formatUpdated(member.last_updated)}
          </span>
        </button>
      {/each}
    </div>

    {#if members.length === 0}
      <div class="empty">
        <p>No members yet.</p>
        <small>Chat with homeclaw to start building household memory.</small>
      </div>
    {/if}

    <!-- Detail panel -->
    {#if selectedPerson}
      <div class="detail-panel">
        {#if detailLoading}
          <div class="loading">
            <div class="loading-dot"></div>
            <div class="loading-dot"></div>
            <div class="loading-dot"></div>
          </div>
        {:else if topicContents}
          <div class="detail-header">
            <h2>{selectedPerson}'s memory</h2>
          </div>

          {#if Object.keys(topicContents).length === 0}
            <p class="empty-detail">No memories stored yet for {selectedPerson}.</p>
          {:else}
            {#each Object.entries(topicContents) as [topic, content]}
              <div class="topic-card">
                <h3>{topic}</h3>
                <pre class="topic-content">{content}</pre>
              </div>
            {/each}
          {/if}

          <!-- Semantic search -->
          {#if semanticReady}
            <div class="search-section">
              <h3>Recall</h3>
              <form class="search-form" onsubmit={(e) => { e.preventDefault(); doSearch(); }}>
                <input
                  class="search-input"
                  type="text"
                  placeholder="Search memories..."
                  bind:value={searchQuery}
                />
                <button class="search-btn" type="submit" disabled={searching || !searchQuery.trim()}>
                  {searching ? "..." : "Search"}
                </button>
              </form>

              {#if searchResults}
                {#if searchResults.note}
                  <p class="search-note">{searchResults.note}</p>
                {:else if searchResults.results.length === 0}
                  <p class="search-note">No results for "{searchResults.query}"</p>
                {:else}
                  <ul class="recall-results">
                    {#each searchResults.results as result}
                      <li>
                        <p class="recall-text">{result.text}</p>
                        <span class="recall-score">{(result.score * 100).toFixed(0)}%</span>
                      </li>
                    {/each}
                  </ul>
                {/if}
              {/if}
            </div>
          {/if}
        {/if}
      </div>
    {/if}
  {/if}
</div>

<style>
  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .memory-page {
    animation: fadeUp 0.35s ease-out;
  }

  .mem-header h1 {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 1.6rem;
    margin: 0 0 1.25rem;
    letter-spacing: -0.02em;
    color: var(--text);
  }

  /* ---- Member list ---- */
  .member-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .member-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 1rem;
    background: var(--surface);
    border: none;
    border-radius: var(--radius);
    cursor: pointer;
    text-align: left;
    font-family: var(--font-sans);
    transition: background 0.15s, box-shadow 0.15s;
    opacity: 0;
    animation: fadeUp 0.3s ease-out forwards;
  }

  .member-card:hover {
    background: var(--surface-low);
    box-shadow: inset 0 0 0 1px rgba(198, 200, 184, 0.2);
  }

  .member-card.active {
    background: var(--surface-low);
    box-shadow: inset 0 0 0 1px rgba(198, 200, 184, 0.2);
    color: var(--primary);
  }

  .member-info {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }

  .member-name {
    font-weight: 600;
    font-size: 0.92rem;
    color: var(--text);
    text-transform: capitalize;
  }

  .member-stats {
    font-size: 0.78rem;
    color: var(--text-muted);
  }

  .member-updated {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  /* ---- Detail panel ---- */
  .detail-panel {
    margin-top: 1rem;
    background: var(--surface);
    border: none;
    border-radius: var(--radius);
    padding: 1.25rem 1.5rem;
    animation: fadeUp 0.25s ease-out;
  }

  .detail-header {
    margin-bottom: 1rem;
  }

  .detail-header h2 {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 1.05rem;
    margin: 0;
    color: var(--text);
    text-transform: capitalize;
  }

  /* ---- Topic cards ---- */
  .topic-card {
    margin-bottom: 1rem;
    padding: 0.75rem 1rem;
    background: var(--surface-low);
    border-radius: var(--radius-md);
  }

  .topic-card h3 {
    font-family: var(--font-serif);
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--primary);
    margin: 0 0 0.5rem;
    text-transform: capitalize;
  }

  .topic-content {
    font-family: var(--font-sans);
    font-size: 0.84rem;
    line-height: 1.5;
    color: var(--text);
    margin: 0;
    white-space: pre-wrap;
    word-wrap: break-word;
  }

  .empty-detail {
    font-family: var(--font-serif);
    font-style: italic;
    color: var(--text-muted);
    font-size: 0.9rem;
  }

  /* ---- Semantic search ---- */
  .search-section {
    margin-top: 2rem;
    padding-top: 0;
  }

  .search-section h3 {
    font-family: var(--font-serif);
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--text-muted);
    margin: 0 0 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .search-form {
    display: flex;
    gap: 0.4rem;
  }

  .search-input {
    flex: 1;
    padding: 0.45rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    font-family: var(--font-sans);
    font-size: 0.85rem;
    color: var(--text);
    background: var(--surface-low);
  }

  .search-input:focus {
    outline: none;
    border-color: var(--primary);
  }

  .search-input::placeholder {
    color: var(--text-muted);
  }

  .search-btn {
    padding: 0.45rem 0.85rem;
    border: none;
    border-radius: var(--radius-pill);
    background: var(--surface-low);
    color: var(--text);
    font-family: var(--font-sans);
    font-size: 0.82rem;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s;
  }

  .search-btn:hover:not(:disabled) {
    background: var(--surface-low);
  }

  .search-btn:disabled {
    opacity: 0.4;
    cursor: default;
  }

  .search-note {
    margin: 0.75rem 0 0;
    font-size: 0.82rem;
    font-style: italic;
    color: var(--text-muted);
  }

  .recall-results {
    list-style: none;
    margin: 0.75rem 0 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .recall-results li {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.5rem 0;
  }

  .recall-text {
    margin: 0;
    font-size: 0.85rem;
    line-height: 1.4;
    color: var(--text);
    flex: 1;
  }

  .recall-score {
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--text-muted);
    background: var(--surface-low);
    padding: 0.1rem 0.4rem;
    border-radius: var(--radius-sm);
    flex-shrink: 0;
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

  .empty small {
    font-size: 0.82rem;
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

  .error-card {
    background: #fef2f0;
    border: none;
    border-radius: var(--radius);
    padding: 1.5rem;
    text-align: center;
    color: var(--secondary);
  }

  .error-card p { margin: 0 0 0.5rem; font-weight: 500; }
  .error-card small { color: var(--text-muted); }
</style>

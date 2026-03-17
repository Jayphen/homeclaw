<script lang="ts">
  interface MemberSummary {
    person: string;
    fact_count: number;
    preference_count: number;
    last_updated: string | null;
  }

  interface MemoryDetail {
    person: string;
    facts: string[];
    preferences: Record<string, string>;
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
  let detail: MemoryDetail | null = $state(null);
  let detailLoading: boolean = $state(false);
  let editing: boolean = $state(false);
  let editFacts: string = $state("");
  let editPrefs: Array<{ key: string; value: string }> = $state([]);
  let saving: boolean = $state(false);

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
      const r = await fetch("/api/memory");
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
      detail = null;
      editing = false;
      searchResults = null;
      return;
    }
    selectedPerson = person;
    detailLoading = true;
    editing = false;
    searchResults = null;
    searchQuery = "";
    try {
      const r = await fetch(`/api/memory/${person}`);
      if (!r.ok) throw new Error(`${r.status}`);
      detail = await r.json();
      detailLoading = false;
    } catch (e: any) {
      error = e.message;
      detailLoading = false;
    }
  }

  function startEditing() {
    if (!detail) return;
    editFacts = detail.facts.join("\n");
    editPrefs = Object.entries(detail.preferences).map(([key, value]) => ({ key, value }));
    editing = true;
  }

  function cancelEditing() {
    editing = false;
  }

  function addPref() {
    editPrefs = [...editPrefs, { key: "", value: "" }];
  }

  function removePref(index: number) {
    editPrefs = editPrefs.filter((_, i) => i !== index);
  }

  async function saveEdits() {
    if (!selectedPerson) return;
    saving = true;
    const facts = editFacts.split("\n").map((f) => f.trim()).filter(Boolean);
    const preferences: Record<string, string> = {};
    for (const p of editPrefs) {
      if (p.key.trim()) preferences[p.key.trim()] = p.value.trim();
    }
    try {
      const r = await fetch(`/api/memory/${selectedPerson}/facts`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ facts, preferences }),
      });
      if (!r.ok) throw new Error(`${r.status}`);
      // Reload detail
      await selectPerson(selectedPerson);
      editing = false;
    } catch (e: any) {
      error = e.message;
    }
    saving = false;
  }

  async function doSearch() {
    if (!selectedPerson || !searchQuery.trim()) return;
    searching = true;
    try {
      const r = await fetch(
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
              {member.fact_count} facts · {member.preference_count} preferences
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
        {:else if detail}
          <div class="detail-header">
            <h2>{detail.person}'s memory</h2>
            {#if !editing}
              <button class="edit-btn" onclick={startEditing}>Edit</button>
            {/if}
          </div>

          {#if editing}
            <!-- Edit mode -->
            <div class="edit-section">
              <label class="edit-label" for="edit-facts">Facts <small>(one per line)</small></label>
              <textarea
                id="edit-facts"
                class="edit-textarea"
                bind:value={editFacts}
                rows="8"
              ></textarea>

              <span class="edit-label">Preferences</span>
              <div class="pref-list">
                {#each editPrefs as pref, i}
                  <div class="pref-row">
                    <input
                      class="pref-key"
                      placeholder="key"
                      bind:value={pref.key}
                    />
                    <input
                      class="pref-value"
                      placeholder="value"
                      bind:value={pref.value}
                    />
                    <button class="pref-remove" onclick={() => removePref(i)}>×</button>
                  </div>
                {/each}
                <button class="pref-add" onclick={addPref}>+ Add preference</button>
              </div>

              <div class="edit-actions">
                <button class="save-btn" onclick={saveEdits} disabled={saving}>
                  {saving ? "Saving…" : "Save"}
                </button>
                <button class="cancel-btn" onclick={cancelEditing}>Cancel</button>
              </div>
            </div>
          {:else}
            <!-- View mode -->
            {#if detail.facts.length > 0}
              <div class="section">
                <h3>Facts</h3>
                <ul class="fact-list">
                  {#each detail.facts as fact}
                    <li>{fact}</li>
                  {/each}
                </ul>
              </div>
            {/if}

            {#if Object.keys(detail.preferences).length > 0}
              <div class="section">
                <h3>Preferences</h3>
                <div class="pref-grid">
                  {#each Object.entries(detail.preferences) as [key, value]}
                    <div class="pref-item">
                      <span class="pref-key-label">{key}</span>
                      <span class="pref-value-label">{value}</span>
                    </div>
                  {/each}
                </div>
              </div>
            {/if}

            {#if detail.facts.length === 0 && Object.keys(detail.preferences).length === 0}
              <p class="empty-detail">No memories stored yet for {detail.person}.</p>
            {/if}

            <!-- Semantic search -->
            {#if semanticReady}
              <div class="search-section">
                <h3>Recall</h3>
                <form class="search-form" onsubmit={(e) => { e.preventDefault(); doSearch(); }}>
                  <input
                    class="search-input"
                    type="text"
                    placeholder="Search memories…"
                    bind:value={searchQuery}
                  />
                  <button class="search-btn" type="submit" disabled={searching || !searchQuery.trim()}>
                    {searching ? "…" : "Search"}
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
    border: 1px solid var(--border);
    border-radius: var(--radius);
    cursor: pointer;
    text-align: left;
    font-family: var(--font-sans);
    transition: border-color 0.15s, background 0.15s;
    opacity: 0;
    animation: fadeUp 0.3s ease-out forwards;
  }

  .member-card:hover {
    border-color: #d0c8be;
  }

  .member-card.active {
    border-color: var(--terracotta);
    background: #fef9f4;
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
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.25rem 1.5rem;
    animation: fadeUp 0.25s ease-out;
  }

  .detail-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
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

  .edit-btn {
    padding: 0.3rem 0.7rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--surface);
    color: var(--text-muted);
    font-family: var(--font-sans);
    font-size: 0.78rem;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }

  .edit-btn:hover {
    background: #f0ebe5;
    color: var(--text);
  }

  /* ---- Sections ---- */
  .section {
    margin-bottom: 1.25rem;
  }

  .section h3 {
    font-family: var(--font-serif);
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--text-muted);
    margin: 0 0 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .fact-list {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .fact-list li {
    padding: 0.4rem 0;
    border-top: 1px solid var(--border);
    font-size: 0.88rem;
    color: var(--text);
    line-height: 1.4;
  }

  .fact-list li:first-child {
    border-top: none;
    padding-top: 0;
  }

  /* ---- Preferences grid ---- */
  .pref-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
  }

  @media (max-width: 640px) {
    .pref-grid {
      grid-template-columns: 1fr;
    }
  }

  .pref-item {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
    padding: 0.5rem 0.65rem;
    background: #fdfcfa;
    border-radius: 6px;
    border-left: 3px solid var(--sage);
  }

  .pref-key-label {
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--sage);
    text-transform: capitalize;
    letter-spacing: 0.02em;
  }

  .pref-value-label {
    font-size: 0.85rem;
    color: var(--text);
  }

  .empty-detail {
    font-family: var(--font-serif);
    font-style: italic;
    color: var(--text-muted);
    font-size: 0.9rem;
  }

  /* ---- Edit mode ---- */
  .edit-section {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .edit-label {
    font-family: var(--font-serif);
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--text);
  }

  .edit-label small {
    font-weight: 400;
    color: var(--text-muted);
    font-family: var(--font-sans);
  }

  .edit-textarea {
    width: 100%;
    padding: 0.6rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: 8px;
    font-family: var(--font-sans);
    font-size: 0.85rem;
    line-height: 1.5;
    color: var(--text);
    background: var(--surface);
    resize: vertical;
  }

  .edit-textarea:focus {
    outline: none;
    border-color: var(--terracotta);
  }

  .pref-list {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }

  .pref-row {
    display: flex;
    gap: 0.4rem;
    align-items: center;
  }

  .pref-row input {
    padding: 0.4rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-family: var(--font-sans);
    font-size: 0.82rem;
    color: var(--text);
    background: var(--surface);
  }

  .pref-row input:focus {
    outline: none;
    border-color: var(--terracotta);
  }

  .pref-row .pref-key {
    width: 35%;
  }

  .pref-row .pref-value {
    flex: 1;
  }

  .pref-remove {
    width: 1.6rem;
    height: 1.6rem;
    border: none;
    background: none;
    color: var(--text-muted);
    font-size: 1rem;
    cursor: pointer;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .pref-remove:hover {
    background: #fef2f0;
    color: var(--terracotta);
  }

  .pref-add {
    align-self: flex-start;
    padding: 0.3rem 0.6rem;
    border: 1px dashed var(--border);
    border-radius: 6px;
    background: none;
    color: var(--text-muted);
    font-family: var(--font-sans);
    font-size: 0.78rem;
    cursor: pointer;
  }

  .pref-add:hover {
    border-color: var(--sage);
    color: var(--sage);
  }

  .edit-actions {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.25rem;
  }

  .save-btn {
    padding: 0.4rem 1rem;
    border: none;
    border-radius: 6px;
    background: var(--terracotta);
    color: #fff;
    font-family: var(--font-sans);
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .save-btn:hover {
    opacity: 0.9;
  }

  .save-btn:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .cancel-btn {
    padding: 0.4rem 1rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--surface);
    color: var(--text-muted);
    font-family: var(--font-sans);
    font-size: 0.82rem;
    font-weight: 500;
    cursor: pointer;
  }

  .cancel-btn:hover {
    background: #f0ebe5;
    color: var(--text);
  }

  /* ---- Semantic search ---- */
  .search-section {
    margin-top: 1.25rem;
    padding-top: 1.25rem;
    border-top: 1px solid var(--border);
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
    border-radius: 6px;
    font-family: var(--font-sans);
    font-size: 0.85rem;
    color: var(--text);
    background: var(--surface);
  }

  .search-input:focus {
    outline: none;
    border-color: var(--terracotta);
  }

  .search-input::placeholder {
    color: #c5bdb5;
  }

  .search-btn {
    padding: 0.45rem 0.85rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--surface);
    color: var(--text);
    font-family: var(--font-sans);
    font-size: 0.82rem;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s;
  }

  .search-btn:hover:not(:disabled) {
    background: #f0ebe5;
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
  }

  .recall-results li {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.5rem 0;
    border-top: 1px solid var(--border);
  }

  .recall-results li:first-child {
    border-top: none;
    padding-top: 0;
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
    background: #f0ebe5;
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
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
</style>

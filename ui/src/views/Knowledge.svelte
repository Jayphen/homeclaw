<script lang="ts">
  import { api } from "$lib/api";
  import { renderMarkdown, renderPreviewMarkdown } from "$lib/markdown";
  import MarkdownEditor from "$lib/MarkdownEditor.svelte";
  import { formatRelativeTime } from "$lib/time";
  import { format, parseISO } from "date-fns";

  let { params = {} }: { params?: { person?: string; date?: string } } = $props();

  // --- Types ---

  interface MemberSummary {
    person: string;
    topic_count: number;
    topics: string[];
    last_updated: string | null;
  }

  interface NoteEntry {
    person: string;
    date: string;
    preview: string;
    updated_at: string;
  }

  interface NoteDetail {
    person: string;
    date: string;
    content: string;
    updated_at: string;
  }

  interface RecallResult {
    text: string;
    score: number;
    source?: string;
  }

  // --- State ---

  type Tab = "notes" | "memory";
  let tab: Tab = $state("notes");

  let members: MemberSummary[] = $state([]);
  let notes: NoteEntry[] = $state([]);
  let semanticReady: boolean = $state(false);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);

  // Memory detail
  let selectedPerson: string | null = $state(null);
  let topicContents: Record<string, string> | null = $state(null);
  let detailLoading: boolean = $state(false);

  // Note detail
  let noteDetail: NoteDetail | null = $state(null);
  let editing: boolean = $state(false);
  let editContent: string = $state("");
  let saving: boolean = $state(false);

  // Search
  let searchQuery: string = $state("");
  let searchResults: RecallResult[] | null = $state(null);
  let searching: boolean = $state(false);
  let searchNote: string | null = $state(null);

  // --- Derived ---

  const mode = $derived.by(() => {
    if (params.person && params.date) return "note-detail" as const;
    return "index" as const;
  });

  const groupedNotesByPerson = $derived.by(() => {
    const map = new Map<string, NoteEntry[]>();
    for (const n of notes) {
      const arr = map.get(n.person) || [];
      arr.push(n);
      map.set(n.person, arr);
    }
    return map;
  });

  // --- Helpers ---

  function formatDate(iso: string): string {
    return format(parseISO(iso), "EEEE, MMMM d, yyyy");
  }

  function formatDateShort(iso: string): string {
    return format(parseISO(iso), "MMM d, yyyy");
  }

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

  // --- Data fetching ---

  async function fetchIndex() {
    loading = true;
    error = null;
    try {
      const [memR, notesR] = await Promise.all([
        api("/api/memory"),
        api("/api/notes"),
      ]);
      if (!memR.ok) throw new Error(`memory: ${memR.status}`);
      if (!notesR.ok) throw new Error(`notes: ${notesR.status}`);
      const memData = await memR.json();
      members = memData.members;
      semanticReady = memData.semantic_ready;
      notes = await notesR.json();
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function selectPerson(person: string) {
    if (selectedPerson === person) {
      selectedPerson = null;
      topicContents = null;
      return;
    }
    selectedPerson = person;
    detailLoading = true;
    try {
      const r = await api(`/api/memory/${person}`);
      if (!r.ok) throw new Error(`${r.status}`);
      const data = await r.json();
      topicContents = data.topics;
    } catch (e: any) {
      error = e.message;
    } finally {
      detailLoading = false;
    }
  }

  async function fetchNoteDetail(person: string, date: string) {
    loading = true;
    error = null;
    try {
      const r = await api(`/api/notes/${person}/${date}`);
      if (!r.ok) throw new Error(`${r.status}`);
      noteDetail = await r.json();
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  // --- Note editing ---

  function startEdit() {
    if (noteDetail) {
      editContent = noteDetail.content;
      editing = true;
    }
  }

  function cancelEdit() {
    editing = false;
  }

  async function saveEdit() {
    if (!noteDetail || !params.person || !params.date) return;
    saving = true;
    try {
      const r = await api(`/api/notes/${params.person}/${params.date}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: editContent }),
      });
      if (!r.ok) throw new Error(`${r.status}`);
      noteDetail = await r.json();
      editing = false;
    } catch (e: any) {
      error = e.message;
    } finally {
      saving = false;
    }
  }

  // --- Search ---

  async function doSearch() {
    if (!searchQuery.trim()) return;
    searching = true;
    searchResults = null;
    searchNote = null;
    try {
      // Search across all visible members by picking the first, or use household
      const person = members.length > 0 ? members[0].person : "household";
      const r = await api(
        `/api/memory/${person}/recall?q=${encodeURIComponent(searchQuery.trim())}&top_k=10`,
      );
      if (!r.ok) throw new Error(`${r.status}`);
      const data = await r.json();
      searchResults = data.results;
      if (data.note) searchNote = data.note;
    } catch (e: any) {
      error = e.message;
    } finally {
      searching = false;
    }
  }

  // --- Effects ---

  $effect(() => {
    if (mode === "note-detail" && params.person && params.date) {
      fetchNoteDetail(params.person, params.date);
    } else {
      fetchIndex();
    }
  });
</script>

<div class="knowledge-page">
  {#if mode === "note-detail"}
    <!-- Note detail view -->
    <nav class="breadcrumb">
      <a href="#/knowledge">Knowledge</a>
      <span class="sep">/</span>
      <a href="#/knowledge">{params.person}</a>
      <span class="sep">/</span>
      <span>{params.date ? formatDateShort(params.date) : ""}</span>
    </nav>

    {#if loading}
      <div class="loading">
        <div class="loading-dot"></div>
        <div class="loading-dot"></div>
        <div class="loading-dot"></div>
      </div>
    {:else if error}
      <div class="error-card">
        <p>Couldn't load note.</p>
        <small>{error}</small>
      </div>
    {:else if noteDetail}
      <article class="note-article">
        <header>
          <h1>{formatDate(noteDetail.date)}</h1>
          <div class="note-meta">
            <span class="note-person">{noteDetail.person}</span>
            <span class="note-updated">updated {formatRelativeTime(noteDetail.updated_at)}</span>
            <a class="note-cal-link" href="#/calendar?date={noteDetail.date}">View in calendar</a>
          </div>
        </header>
        {#if editing}
          <div class="note-editor">
            <MarkdownEditor bind:value={editContent} disabled={saving} />
            <div class="editor-actions">
              <button class="btn btn-secondary" onclick={cancelEdit} disabled={saving}>Cancel</button>
              <button class="btn btn-primary" onclick={saveEdit} disabled={saving}>
                {saving ? "Saving..." : "Save"}
              </button>
            </div>
          </div>
        {:else}
          <div class="note-body">
            <button class="btn-edit" onclick={startEdit}>Edit</button>
            {@html renderMarkdown(noteDetail.content)}
          </div>
        {/if}
      </article>
    {/if}
  {:else}
    <!-- Index view -->
    <h1 class="page-title">Knowledge</h1>

    <!-- Semantic search -->
    {#if semanticReady}
      <section class="search-section">
        <form class="search-form" onsubmit={(e) => { e.preventDefault(); doSearch(); }}>
          <input
            class="search-input"
            type="text"
            placeholder="Search notes and memory..."
            bind:value={searchQuery}
          />
          <button class="search-btn" type="submit" disabled={searching || !searchQuery.trim()}>
            {searching ? "..." : "Search"}
          </button>
        </form>

        {#if searchResults}
          {#if searchNote}
            <p class="search-note">{searchNote}</p>
          {:else if searchResults.length === 0}
            <p class="search-note">No results for "{searchQuery}"</p>
          {:else}
            <ul class="recall-results">
              {#each searchResults as result}
                <li>
                  <p class="recall-text">{result.text}</p>
                  <span class="recall-score">{(result.score * 100).toFixed(0)}%</span>
                </li>
              {/each}
            </ul>
          {/if}
        {/if}
      </section>
    {/if}

    <!-- Tab bar -->
    <div class="tab-bar">
      <button class="tab" class:active={tab === "notes"} onclick={() => (tab = "notes")}>
        Notes
        {#if notes.length > 0}<span class="tab-count">{notes.length}</span>{/if}
      </button>
      <button class="tab" class:active={tab === "memory"} onclick={() => (tab = "memory")}>
        Memory
        {#if members.reduce((a, m) => a + m.topic_count, 0) > 0}
          <span class="tab-count">{members.reduce((a, m) => a + m.topic_count, 0)}</span>
        {/if}
      </button>
    </div>

    {#if loading}
      <div class="loading">
        <div class="loading-dot"></div>
        <div class="loading-dot"></div>
        <div class="loading-dot"></div>
      </div>
    {:else if error}
      <div class="error-card">
        <p>Couldn't load data.</p>
        <small>{error}</small>
      </div>
    {:else if tab === "notes"}
      <!-- Notes tab -->
      {#if notes.length === 0}
        <div class="empty">
          <p>No notes yet.</p>
          <small>Chat with homeclaw to create notes for your household.</small>
        </div>
      {:else}
        {#each [...groupedNotesByPerson.entries()] as [person, personNotes], gi}
          <section class="person-section">
            <h2>
              {person}
              <span class="count-badge">{personNotes.length}</span>
            </h2>
            <div class="note-list">
              {#each personNotes.slice(0, 5) as note, i}
                <a
                  class="note-card"
                  href="#/knowledge/{note.person}/{note.date}"
                >
                  <div class="note-card-header">
                    <span class="note-card-date">{formatDateShort(note.date)}</span>
                    <span class="note-card-updated">{formatRelativeTime(note.updated_at)}</span>
                  </div>
                  <div class="note-card-preview">{@html renderPreviewMarkdown(note.preview)}</div>
                </a>
              {/each}
              {#if personNotes.length > 5}
                <p class="show-more">{personNotes.length - 5} more notes</p>
              {/if}
            </div>
          </section>
        {/each}
      {/if}
    {:else}
      <!-- Memory tab -->
      {#if members.length === 0}
        <div class="empty">
          <p>No members yet.</p>
          <small>Chat with homeclaw to start building household memory.</small>
        </div>
      {:else}
        <div class="member-list">
          {#each members as member, i}
            {@const isActive = selectedPerson === member.person}
            <button
              class="member-card"
              class:active={isActive}
              onclick={() => selectPerson(member.person)}
            >
              <div class="member-info">
                <span class="member-name">{member.person}</span>
                <span class="member-stats">
                  {member.topic_count} {member.topic_count === 1 ? "topic" : "topics"}
                </span>
              </div>
              <span class="member-updated">{formatUpdated(member.last_updated)}</span>
            </button>
          {/each}
        </div>

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
            {/if}
          </div>
        {/if}
      {/if}
    {/if}
  {/if}
</div>

<style>
  .page-title {
    font-family: var(--font-serif); font-weight: 600; font-size: 1.6rem;
    margin: 0 0 1.25rem; letter-spacing: -0.02em; color: var(--text);
  }

  /* ---- Breadcrumb ---- */
  .breadcrumb { display: flex; align-items: center; gap: 0.35rem; margin-bottom: 1rem; font-size: 0.82rem; }
  .breadcrumb a { color: var(--primary); text-decoration: none; text-transform: capitalize; }
  .breadcrumb a:hover { text-decoration: underline; }
  .breadcrumb span { color: var(--text-muted); }
  .sep { color: var(--border); }

  /* ---- Search ---- */
  .search-section {
    background: var(--surface); border-radius: var(--radius);
    padding: 1rem 1.25rem; margin-bottom: 1.25rem;
  }
  .search-form { display: flex; gap: 0.4rem; }
  .search-input {
    flex: 1; padding: 0.5rem 0.85rem; border: 1px solid var(--border);
    border-radius: var(--radius-md); font-family: var(--font-sans);
    font-size: 0.88rem; color: var(--text); background: var(--surface-low);
  }
  .search-input:focus { outline: none; border-color: var(--primary); }
  .search-input::placeholder { color: var(--text-muted); }
  .search-btn {
    padding: 0.5rem 1rem; border: none; border-radius: var(--radius-pill);
    background: var(--primary); color: #fff; font-family: var(--font-sans);
    font-size: 0.82rem; font-weight: 500; cursor: pointer; transition: opacity 0.15s;
  }
  .search-btn:hover:not(:disabled) { opacity: 0.9; }
  .search-btn:disabled { opacity: 0.4; cursor: default; }
  .search-note { margin: 0.75rem 0 0; font-size: 0.82rem; font-style: italic; color: var(--text-muted); }
  .recall-results { list-style: none; margin: 0.75rem 0 0; padding: 0; display: flex; flex-direction: column; gap: 0.5rem; }
  .recall-results li { display: flex; align-items: flex-start; gap: 0.75rem; padding: 0.5rem 0; }
  .recall-text { margin: 0; font-size: 0.85rem; line-height: 1.4; color: var(--text); flex: 1; }
  .recall-score {
    font-size: 0.72rem; font-weight: 600; color: var(--text-muted);
    background: var(--surface-low); padding: 0.1rem 0.4rem; border-radius: var(--radius-sm); flex-shrink: 0;
  }

  /* ---- Tabs ---- */
  .tab-bar {
    display: flex; gap: 0.25rem; margin-bottom: 1.25rem;
    border-bottom: 1px solid var(--border); padding-bottom: 0;
  }
  .tab {
    padding: 0.5rem 1rem; border: none; background: none;
    font-family: var(--font-sans); font-size: 0.85rem; font-weight: 500;
    color: var(--text-muted); cursor: pointer; position: relative;
    transition: color 0.15s; display: flex; align-items: center; gap: 0.4rem;
  }
  .tab:hover { color: var(--text); }
  .tab.active { color: var(--text); }
  .tab.active::after {
    content: ""; position: absolute; bottom: -1px; left: 0; right: 0;
    height: 2px; background: var(--primary); border-radius: 1px;
  }
  .tab-count {
    font-size: 0.7rem; font-weight: 600; color: var(--text-muted);
    background: var(--surface-low); padding: 0.05rem 0.35rem; border-radius: var(--radius-sm);
  }

  /* ---- Notes tab ---- */
  .person-section { margin-bottom: 2rem; }
  .person-section h2 {
    font-family: var(--font-serif); font-weight: 600; font-size: 1.1rem;
    margin: 0 0 0.75rem; display: flex; align-items: center; gap: 0.5rem;
    text-transform: capitalize;
  }
  .count-badge {
    font-family: var(--font-sans); font-size: 0.72rem; font-weight: 600;
    color: var(--text-muted); background: var(--surface-low);
    padding: 0.1rem 0.45rem; border-radius: var(--radius-sm);
  }
  .note-list { display: flex; flex-direction: column; gap: 0.5rem; }
  .note-card {
    display: block; padding: 0.75rem 1rem; background: var(--surface);
    border-radius: var(--radius); text-decoration: none; color: var(--text);
    transition: background 0.15s;
  }
  .note-card:hover { background: var(--surface-low); box-shadow: inset 0 0 0 1px rgba(198, 200, 184, 0.2); }
  .note-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.3rem; }
  .note-card-date { font-weight: 600; font-size: 0.85rem; color: var(--text); }
  .note-card-updated { font-size: 0.72rem; color: var(--text-muted); }
  .note-card-preview {
    margin: 0; font-size: 0.82rem; color: var(--text-muted); line-height: 1.4;
    overflow: hidden; text-overflow: ellipsis; display: -webkit-box;
    -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  }
  .note-card-preview :global(p) { margin: 0; }
  .note-card-preview :global(ul), .note-card-preview :global(ol) { margin: 0; padding-left: 1.2rem; }
  .note-card-preview :global(h1), .note-card-preview :global(h2),
  .note-card-preview :global(h3), .note-card-preview :global(h4) { font-size: inherit; font-weight: 600; margin: 0; }
  .show-more { font-size: 0.82rem; color: var(--text-muted); text-align: center; padding: 0.5rem; margin: 0; }

  /* ---- Memory tab ---- */
  .member-list { display: flex; flex-direction: column; gap: 0.5rem; }
  .member-card {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0.75rem 1rem; background: var(--surface); border: none;
    border-radius: var(--radius); cursor: pointer; text-align: left;
    font-family: var(--font-sans); transition: background 0.15s, box-shadow 0.15s;
  }
  .member-card:hover { background: var(--surface-low); box-shadow: inset 0 0 0 1px rgba(198, 200, 184, 0.2); }
  .member-card.active { background: var(--surface-low); box-shadow: inset 0 0 0 1px rgba(198, 200, 184, 0.2); color: var(--primary); }
  .member-info { display: flex; flex-direction: column; gap: 0.15rem; }
  .member-name { font-weight: 600; font-size: 0.92rem; color: var(--text); text-transform: capitalize; }
  .member-stats { font-size: 0.78rem; color: var(--text-muted); }
  .member-updated { font-size: 0.75rem; color: var(--text-muted); }

  .detail-panel {
    margin-top: 1rem; background: var(--surface); border-radius: var(--radius);
    padding: 1.25rem 1.5rem;
  }
  .detail-header { margin-bottom: 1rem; }
  .detail-header h2 {
    font-family: var(--font-serif); font-weight: 600; font-size: 1.05rem;
    margin: 0; color: var(--text); text-transform: capitalize;
  }
  .topic-card { margin-bottom: 1rem; padding: 0.75rem 1rem; background: var(--surface-low); border-radius: var(--radius-md); }
  .topic-card h3 {
    font-family: var(--font-serif); font-size: 0.85rem; font-weight: 600;
    color: var(--primary); margin: 0 0 0.5rem; text-transform: capitalize;
  }
  .topic-content {
    font-family: var(--font-sans); font-size: 0.84rem; line-height: 1.5;
    color: var(--text); margin: 0; white-space: pre-wrap; word-wrap: break-word;
  }
  .empty-detail { font-family: var(--font-serif); font-style: italic; color: var(--text-muted); font-size: 0.9rem; }

  /* ---- Note detail ---- */
  .note-article { background: var(--surface); border-radius: var(--radius); padding: 1.5rem 2rem; }
  .note-article header { margin-bottom: 1.5rem; padding-bottom: 1rem; }
  .note-article h1 {
    font-family: var(--font-serif); font-weight: 600; font-size: 1.4rem;
    margin: 0 0 0.5rem; letter-spacing: -0.02em; color: var(--text);
  }
  .note-meta { display: flex; align-items: center; gap: 0.75rem; font-size: 0.78rem; }
  .note-person { font-weight: 600; color: var(--sage); text-transform: capitalize; }
  .note-updated { color: var(--text-muted); }
  .note-cal-link { color: var(--primary); text-decoration: none; margin-left: auto; }
  .note-cal-link:hover { text-decoration: underline; }

  .note-body { font-size: 0.92rem; line-height: 1.65; color: var(--text); }
  .note-body :global(h1), .note-body :global(h2), .note-body :global(h3) { font-family: var(--font-serif); margin: 1.25rem 0 0.5rem; }
  .note-body :global(h2) { font-size: 1.1rem; }
  .note-body :global(h3) { font-size: 0.95rem; }
  .note-body :global(p) { margin: 0.5rem 0; }
  .note-body :global(ul), .note-body :global(ol) { margin: 0.5rem 0; padding-left: 1.5rem; }
  .note-body :global(li) { margin: 0.2rem 0; }
  .note-body :global(strong) { font-weight: 600; }
  .note-body :global(a) { color: var(--primary); text-decoration: underline; text-decoration-color: rgba(86, 100, 43, 0.3); }
  .note-body :global(a:hover) { text-decoration-color: var(--primary); }
  .note-body :global(code) { background: var(--surface-low); padding: 0.1rem 0.3rem; border-radius: var(--radius-sm); font-size: 0.85em; }
  .note-body :global(table) { width: 100%; border-collapse: collapse; margin: 0.75rem 0; font-size: 0.85rem; }
  .note-body :global(th), .note-body :global(td) { padding: 0.4rem 0.6rem; border: none; text-align: left; }
  .note-body :global(th) { background: var(--surface-low); font-weight: 600; }
  .note-body :global(blockquote) { margin: 0.75rem 0; padding: 0.75rem 1rem; background: var(--surface-low); color: var(--text-muted); }
  .note-body :global(hr) { border: none; background: var(--surface-low); height: 2px; margin: 1.25rem 0; }

  /* ---- Buttons ---- */
  .btn-edit {
    float: right; background: var(--surface-low); border: none; border-radius: var(--radius-pill);
    padding: 0.3rem 0.75rem; font-size: 0.78rem; color: var(--text-muted);
    cursor: pointer; transition: background 0.15s, color 0.15s;
  }
  .btn-edit:hover { background: var(--primary); color: #fff; }
  .note-editor { display: flex; flex-direction: column; gap: 0.75rem; }
  .editor-actions { display: flex; justify-content: flex-end; gap: 0.5rem; }
  .btn { padding: 0.4rem 1rem; border-radius: var(--radius); font-size: 0.82rem; font-weight: 500; cursor: pointer; transition: background 0.15s; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-secondary { background: var(--surface-low); border: none; color: var(--text-muted); border-radius: var(--radius-pill); }
  .btn-secondary:hover:not(:disabled) { color: var(--text); }
  .btn-primary { background: var(--primary); border: none; color: #fff; border-radius: var(--radius-pill); }
  .btn-primary:hover:not(:disabled) { opacity: 0.9; }

  /* ---- Empty & loading ---- */
  .empty { text-align: center; padding: 3rem 1rem; color: var(--text-muted); }
  .empty p { font-family: var(--font-serif); font-style: italic; font-size: 1.1rem; margin: 0 0 0.5rem; }
  .empty small { font-size: 0.82rem; }
  .loading { display: flex; justify-content: center; gap: 0.5rem; padding: 4rem 0; }
  .loading-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--primary); opacity: 0.3; animation: pulse 1s ease-in-out infinite; }
  .loading-dot:nth-child(2) { animation-delay: 0.15s; }
  .loading-dot:nth-child(3) { animation-delay: 0.3s; }
  @keyframes pulse {
    0%, 100% { opacity: 0.3; transform: scale(1); }
    50% { opacity: 1; transform: scale(1.2); }
  }
  .error-card { background: var(--surface-low); border: none; border-radius: var(--radius); padding: 1.5rem; text-align: center; color: var(--secondary); }
  .error-card p { margin: 0 0 0.5rem; font-weight: 500; }
  .error-card small { color: var(--text-muted); }

  @media (max-width: 640px) {
    .note-article { padding: 1rem 1.25rem; }
  }
</style>

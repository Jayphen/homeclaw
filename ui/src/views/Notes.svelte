<script lang="ts">
  import { format, parseISO } from "date-fns";
  import { api } from "$lib/api";
  import { renderMarkdown, renderInlineMarkdown } from "$lib/markdown";
  import MarkdownEditor from "$lib/MarkdownEditor.svelte";

  // Route params from svelte-spa-router
  let { params = {} }: { params?: { person?: string; date?: string } } = $props();

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

  let index: NoteEntry[] = $state([]);
  let detail: NoteDetail | null = $state(null);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);
  let editing: boolean = $state(false);
  let editContent: string = $state("");
  let saving: boolean = $state(false);

  const mode = $derived.by(() => {
    if (params.person && params.date) return "detail" as const;
    if (params.person) return "person" as const;
    return "index" as const;
  });

  function formatDate(iso: string): string {
    return format(parseISO(iso), "EEEE, MMMM d, yyyy");
  }

  function formatDateShort(iso: string): string {
    return format(parseISO(iso), "MMM d, yyyy");
  }

  function formatTime(iso: string): string {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return "just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays === 1) return "yesterday";
    return `${diffDays}d ago`;
  }

  // Group notes by person for the index view
  const groupedByPerson = $derived.by(() => {
    const map = new Map<string, NoteEntry[]>();
    for (const n of index) {
      const arr = map.get(n.person) || [];
      arr.push(n);
      map.set(n.person, arr);
    }
    return map;
  });

  async function fetchIndex() {
    loading = true;
    error = null;
    try {
      const r = await api("/api/notes");
      if (!r.ok) throw new Error(`${r.status}`);
      index = await r.json();
      loading = false;
    } catch (e: any) {
      error = e.message;
      loading = false;
    }
  }

  async function fetchPersonNotes(person: string) {
    loading = true;
    error = null;
    try {
      const r = await api(`/api/notes/${person}`);
      if (!r.ok) throw new Error(`${r.status}`);
      const notes: Array<{ date: string; preview: string; updated_at: string }> = await r.json();
      index = notes.map((n) => ({ ...n, person }));
      loading = false;
    } catch (e: any) {
      error = e.message;
      loading = false;
    }
  }

  async function fetchDetail(person: string, date: string) {
    loading = true;
    error = null;
    try {
      const r = await api(`/api/notes/${person}/${date}`);
      if (!r.ok) throw new Error(`${r.status}`);
      detail = await r.json();
      loading = false;
    } catch (e: any) {
      error = e.message;
      loading = false;
    }
  }

  function startEdit() {
    if (detail) {
      editContent = detail.content;
      editing = true;
    }
  }

  function cancelEdit() {
    editing = false;
  }

  async function saveEdit() {
    if (!detail || !params.person || !params.date) return;
    saving = true;
    try {
      const r = await api(`/api/notes/${params.person}/${params.date}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: editContent }),
      });
      if (!r.ok) throw new Error(`${r.status}`);
      detail = await r.json();
      editing = false;
    } catch (e: any) {
      error = e.message;
    } finally {
      saving = false;
    }
  }

  $effect(() => {
    if (mode === "detail" && params.person && params.date) {
      fetchDetail(params.person, params.date);
    } else if (mode === "person" && params.person) {
      fetchPersonNotes(params.person);
    } else {
      fetchIndex();
    }
  });
</script>

<div class="notes-page">
  <!-- Breadcrumb -->
  <nav class="breadcrumb">
    <a href="#/notes">Notes</a>
    {#if params.person}
      <span class="sep">/</span>
      <a href="#/notes/{params.person}">{params.person}</a>
    {/if}
    {#if params.date}
      <span class="sep">/</span>
      <span>{formatDateShort(params.date)}</span>
    {/if}
  </nav>

  {#if loading}
    <div class="loading">
      <div class="loading-dot"></div>
      <div class="loading-dot"></div>
      <div class="loading-dot"></div>
    </div>
  {:else if error}
    <div class="error-card">
      <p>Couldn't load notes.</p>
      <small>{error}</small>
    </div>
  {:else if mode === "detail" && detail}
    <!-- Full note view -->
    <article class="note-article">
      <header>
        <h1>{formatDate(detail.date)}</h1>
        <div class="note-meta">
          <span class="note-person">{detail.person}</span>
          <span class="note-updated">updated {formatTime(detail.updated_at)}</span>
          <a class="note-cal-link" href="#/calendar?date={detail.date}">View in calendar</a>
        </div>
      </header>
      {#if editing}
        <div class="note-editor">
          <MarkdownEditor bind:value={editContent} disabled={saving} />
          <div class="editor-actions">
            <button class="btn btn-secondary" onclick={cancelEdit} disabled={saving}>Cancel</button>
            <button class="btn btn-primary" onclick={saveEdit} disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      {:else}
        <div class="note-body">
          <button class="btn-edit" onclick={startEdit} title="Edit note">Edit</button>
          {@html renderMarkdown(detail.content)}
        </div>
      {/if}
    </article>
  {:else if mode === "person"}
    <!-- Person's notes list -->
    <h1 class="page-title">{params.person}'s notes</h1>
    {#if index.length === 0}
      <div class="empty">
        <p>No notes yet.</p>
      </div>
    {:else}
      <div class="note-list">
        {#each index as note, i}
          <a
            class="note-card"
            href="#/notes/{note.person}/{note.date}"
            style="animation-delay: {i * 40}ms"
          >
            <div class="note-card-header">
              <span class="note-card-date">{formatDateShort(note.date)}</span>
              <span class="note-card-updated">{formatTime(note.updated_at)}</span>
            </div>
            <p class="note-card-preview">{@html renderInlineMarkdown(note.preview)}</p>
          </a>
        {/each}
      </div>
    {/if}
  {:else}
    <!-- All notes index -->
    <h1 class="page-title">Notes</h1>
    {#if index.length === 0}
      <div class="empty">
        <p>No notes yet.</p>
        <small>Chat with homeclaw to create notes for your household.</small>
      </div>
    {:else}
      {#each [...groupedByPerson.entries()] as [person, notes], gi}
        <section class="person-section" style="animation-delay: {gi * 60}ms">
          <h2>
            <a href="#/notes/{person}">{person}</a>
            <span class="note-count">{notes.length}</span>
          </h2>
          <div class="note-list">
            {#each notes.slice(0, 5) as note, i}
              <a
                class="note-card"
                href="#/notes/{note.person}/{note.date}"
                style="animation-delay: {(gi * 60) + (i * 40)}ms"
              >
                <div class="note-card-header">
                  <span class="note-card-date">{formatDateShort(note.date)}</span>
                  <span class="note-card-updated">{formatTime(note.updated_at)}</span>
                </div>
                <p class="note-card-preview">{@html renderInlineMarkdown(note.preview)}</p>
              </a>
            {/each}
            {#if notes.length > 5}
              <a class="show-all" href="#/notes/{person}">
                View all {notes.length} notes
              </a>
            {/if}
          </div>
        </section>
      {/each}
    {/if}
  {/if}
</div>

<style>
  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .notes-page {
    animation: fadeUp 0.35s ease-out;
  }

  /* ---- Breadcrumb ---- */
  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    margin-bottom: 1rem;
    font-size: 0.82rem;
  }

  .breadcrumb a {
    color: var(--terracotta);
    text-decoration: none;
    text-transform: capitalize;
  }

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  .breadcrumb span {
    color: var(--text-muted);
  }

  .sep {
    color: var(--border);
  }

  /* ---- Page title ---- */
  .page-title {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 1.6rem;
    margin: 0 0 1.25rem;
    letter-spacing: -0.02em;
    color: var(--text);
    text-transform: capitalize;
  }

  /* ---- Person sections ---- */
  .person-section {
    margin-bottom: 2rem;
    opacity: 0;
    animation: fadeUp 0.3s ease-out forwards;
  }

  .person-section h2 {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 1.1rem;
    margin: 0 0 0.75rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .person-section h2 a {
    color: var(--text);
    text-decoration: none;
    text-transform: capitalize;
  }

  .person-section h2 a:hover {
    color: var(--terracotta);
  }

  .note-count {
    font-family: var(--font-sans);
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--text-muted);
    background: #f0ebe5;
    padding: 0.1rem 0.45rem;
    border-radius: 4px;
  }

  /* ---- Note cards ---- */
  .note-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .note-card {
    display: block;
    padding: 0.75rem 1rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    text-decoration: none;
    color: var(--text);
    transition: border-color 0.15s, background 0.15s;
    opacity: 0;
    animation: fadeUp 0.3s ease-out forwards;
  }

  .note-card:hover {
    border-color: var(--terracotta);
    background: #fef9f4;
  }

  .note-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.3rem;
  }

  .note-card-date {
    font-weight: 600;
    font-size: 0.85rem;
    color: var(--text);
  }

  .note-card-updated {
    font-size: 0.72rem;
    color: var(--text-muted);
  }

  .note-card-preview {
    margin: 0;
    font-size: 0.82rem;
    color: var(--text-muted);
    line-height: 1.4;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }

  .show-all {
    display: block;
    padding: 0.5rem;
    text-align: center;
    font-size: 0.82rem;
    color: var(--terracotta);
    text-decoration: none;
  }

  .show-all:hover {
    text-decoration: underline;
  }

  /* ---- Note article (detail view) ---- */
  .note-article {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.5rem 2rem;
  }

  .note-article header {
    margin-bottom: 1.5rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--border);
  }

  .note-article h1 {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 1.4rem;
    margin: 0 0 0.5rem;
    letter-spacing: -0.02em;
    color: var(--text);
  }

  .note-meta {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-size: 0.78rem;
  }

  .note-person {
    font-weight: 600;
    color: var(--sage);
    text-transform: capitalize;
  }

  .note-updated {
    color: var(--text-muted);
  }

  .note-cal-link {
    color: var(--terracotta);
    text-decoration: none;
    margin-left: auto;
  }

  .note-cal-link:hover {
    text-decoration: underline;
  }

  /* ---- Markdown body ---- */
  .note-body {
    font-size: 0.92rem;
    line-height: 1.65;
    color: var(--text);
  }

  .note-body :global(h1),
  .note-body :global(h2),
  .note-body :global(h3) {
    font-family: var(--font-serif);
    margin: 1.25rem 0 0.5rem;
    color: var(--text);
  }

  .note-body :global(h2) { font-size: 1.1rem; }
  .note-body :global(h3) { font-size: 0.95rem; }

  .note-body :global(p) {
    margin: 0.5rem 0;
  }

  .note-body :global(ul),
  .note-body :global(ol) {
    margin: 0.5rem 0;
    padding-left: 1.5rem;
  }

  .note-body :global(li) {
    margin: 0.2rem 0;
  }

  .note-body :global(strong) {
    font-weight: 600;
  }

  .note-body :global(a) {
    color: var(--terracotta);
    text-decoration: underline;
    text-decoration-color: rgba(196, 101, 58, 0.3);
  }

  .note-body :global(a:hover) {
    text-decoration-color: var(--terracotta);
  }

  .note-body :global(code) {
    background: #f0ebe5;
    padding: 0.1rem 0.3rem;
    border-radius: 3px;
    font-size: 0.85em;
  }

  .note-body :global(table) {
    width: 100%;
    border-collapse: collapse;
    margin: 0.75rem 0;
    font-size: 0.85rem;
  }

  .note-body :global(th),
  .note-body :global(td) {
    padding: 0.4rem 0.6rem;
    border: 1px solid var(--border);
    text-align: left;
  }

  .note-body :global(th) {
    background: #f5f0ea;
    font-weight: 600;
  }

  .note-body :global(blockquote) {
    margin: 0.75rem 0;
    padding: 0.5rem 1rem;
    border-left: 3px solid var(--sage);
    background: #fdfcfa;
    color: var(--text-muted);
  }

  .note-body :global(hr) {
    border: none;
    border-top: 1px solid var(--border);
    margin: 1.25rem 0;
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

  /* ---- Edit button ---- */
  .btn-edit {
    float: right;
    background: none;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.3rem 0.75rem;
    font-size: 0.78rem;
    color: var(--text-muted);
    cursor: pointer;
    transition: border-color 0.15s, color 0.15s;
  }

  .btn-edit:hover {
    border-color: var(--terracotta);
    color: var(--terracotta);
  }

  /* ---- Editor ---- */
  .note-editor {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

.editor-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
  }

  .btn {
    padding: 0.4rem 1rem;
    border-radius: var(--radius);
    font-size: 0.82rem;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-secondary {
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text-muted);
  }

  .btn-secondary:hover:not(:disabled) {
    border-color: var(--text-muted);
  }

  .btn-primary {
    background: var(--terracotta);
    border: 1px solid var(--terracotta);
    color: #fff;
  }

  .btn-primary:hover:not(:disabled) {
    background: #b35a36;
    border-color: #b35a36;
  }

  @media (max-width: 640px) {
    .note-article {
      padding: 1rem 1.25rem;
    }
  }
</style>

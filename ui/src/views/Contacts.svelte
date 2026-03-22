<script lang="ts">
  import { api } from "$lib/api";
  import { renderMarkdown } from "$lib/markdown";

  // Route params from svelte-spa-router
  let { params = {} }: { params?: { id?: string } } = $props();

  interface ContactSummary {
    id: string;
    name: string;
    nicknames: string[];
    relationship: string;
    birthday: string | null;
    last_contact: string | null;
    reminder_count: number;
    member: string | null;
  }

  interface Interaction {
    date: string;
    type: string;
    notes: string;
  }

  interface ContactReminder {
    interval_days: number | null;
    next_date: string | null;
    note: string;
  }

  interface ContactDetail {
    id: string;
    name: string;
    nicknames: string[];
    relationship: string;
    birthday: string | null;
    interactions: Interaction[];
    reminders: ContactReminder[];
    last_contact: string | null;
    member: string | null;
    notes_md: string | null;
    personal_notes_md: string | null;
  }

  let contacts: ContactSummary[] = $state([]);
  let selected: ContactDetail | null = $state(null);
  let search: string = $state("");
  let loading: boolean = $state(true);
  let detailLoading: boolean = $state(false);
  let error: string | null = $state(null);

  const filtered = $derived.by(() => {
    if (!search.trim()) return contacts;
    const q = search.toLowerCase();
    return contacts.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.relationship.toLowerCase().includes(q) ||
        c.nicknames.some((n) => n.toLowerCase().includes(q)),
    );
  });

  const members = $derived(filtered.filter((c) => c.member));
  const others = $derived(filtered.filter((c) => !c.member));

  function formatDate(iso: string): string {
    const d = new Date(iso + "T12:00:00");
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }

  function formatDateTime(iso: string): string {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }

  function timeAgo(iso: string): string {
    const d = new Date(iso);
    const now = new Date();
    const days = Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
    if (days === 0) return "today";
    if (days === 1) return "yesterday";
    if (days < 30) return `${days}d ago`;
    const months = Math.floor(days / 30);
    if (months < 12) return `${months}mo ago`;
    return `${Math.floor(months / 12)}y ago`;
  }

  function birthdayDisplay(iso: string): string {
    const d = new Date(iso + "T12:00:00");
    return d.toLocaleDateString("en-US", { month: "long", day: "numeric" });
  }

  async function loadContact(id: string) {
    detailLoading = true;
    try {
      const r = await api(`/api/contacts/${id}`);
      if (!r.ok) throw new Error(`${r.status}`);
      selected = await r.json();
    } catch {
      selected = null;
    }
    detailLoading = false;
  }

  $effect(() => {
    api("/api/contacts")
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((d: ContactSummary[]) => {
        contacts = d;
        loading = false;
      })
      .catch((e) => {
        error = e.message;
        loading = false;
      });
  });

  $effect(() => {
    if (params.id) {
      loadContact(params.id);
    } else {
      selected = null;
    }
  });
</script>

{#snippet contactRow(contact: ContactSummary)}
  <a
    class="contact-row"
    href="#/contacts/{contact.id}"
  >
    <div class="contact-avatar" class:member-avatar={contact.member}>
      {contact.name
        .split(" ")
        .map((w) => w[0])
        .join("")
        .slice(0, 2)
        .toUpperCase()}
    </div>
    <div class="contact-info">
      <div class="contact-name">
        {contact.name}
      </div>
      <div class="contact-meta">
        <span>{contact.relationship}</span>
        {#if contact.birthday}
          <span class="sep">&middot;</span>
          <span>{birthdayDisplay(contact.birthday)}</span>
        {/if}
        {#if contact.last_contact}
          <span class="sep">&middot;</span>
          <span>{timeAgo(contact.last_contact)}</span>
        {/if}
      </div>
    </div>
    <div class="contact-arrow">&rsaquo;</div>
  </a>
{/snippet}

{#if loading}
  <div class="loading">
    <div class="loading-dot"></div>
    <div class="loading-dot"></div>
    <div class="loading-dot"></div>
  </div>
{:else if error}
  <div class="error-card">
    <p>Couldn't load contacts</p>
    <small>{error}</small>
  </div>
{:else if contacts.length === 0}
  <div class="empty">
    <p>No contacts yet</p>
    <small>Chat with homeclaw to start building your address book.</small>
  </div>
{:else}
  <header class="page-header">
    <h1>Contacts</h1>
    <p class="subtitle">{contacts.length} {contacts.length === 1 ? "person" : "people"}</p>
  </header>

  <div class="search-bar">
    <input
      type="text"
      placeholder="Search by name, nickname, or relationship..."
      bind:value={search}
    />
  </div>

  {#if selected}
    <!-- Detail panel -->
    <div class="detail-panel">
      <a class="back-btn" href="#/contacts">&larr; All contacts</a>

      {#if detailLoading}
        <div class="loading">
          <div class="loading-dot"></div>
          <div class="loading-dot"></div>
          <div class="loading-dot"></div>
        </div>
      {:else}
        <div class="detail-header">
          <div class="detail-avatar">
            {selected.name
              .split(" ")
              .map((w) => w[0])
              .join("")
              .slice(0, 2)
              .toUpperCase()}
          </div>
          <div>
            <h2>{selected.name}</h2>
            <span class="detail-relationship">{selected.relationship}</span>
            {#if selected.nicknames.length > 0}
              <span class="detail-nicknames">aka {selected.nicknames.join(", ")}</span>
            {/if}
          </div>
        </div>

        {@const hasData = selected.birthday || selected.last_contact || selected.member || selected.notes_md || selected.personal_notes_md || selected.reminders.length > 0 || selected.interactions.length > 0}
        {#if hasData}
        <div class="detail-grid">
          <!-- Info card -->
          {#if selected.birthday || selected.last_contact || selected.member}
          <section class="card info-card">
            {#if selected.birthday}
              <div class="info-row">
                <span class="info-label">Birthday</span>
                <span>{birthdayDisplay(selected.birthday)}</span>
              </div>
            {/if}
            {#if selected.last_contact}
              <div class="info-row">
                <span class="info-label">Last contact</span>
                <span>{formatDateTime(selected.last_contact)} ({timeAgo(selected.last_contact)})</span>
              </div>
            {/if}
            {#if selected.member}
              <div class="info-row">
                <span class="info-label">Member</span>
                <span class="badge member-badge">{selected.member}</span>
              </div>
            {/if}
          </section>
          {/if}

          <!-- Notes -->
          {#if selected.notes_md}
            <section class="card">
              <h3>Notes</h3>
              <div class="contact-notes">{@html renderMarkdown(selected.notes_md)}</div>
            </section>
          {/if}

          <!-- Personal notes -->
          {#if selected.personal_notes_md}
            <section class="card personal-notes-card">
              <h3>Your notes</h3>
              <div class="contact-notes">{@html renderMarkdown(selected.personal_notes_md)}</div>
            </section>
          {/if}

          <!-- Reminders -->
          {#if selected.reminders.length > 0}
            <section class="card">
              <h3>Reminders</h3>
              <ul>
                {#each selected.reminders as reminder}
                  <li>
                    <span class="reminder-note">{reminder.note}</span>
                    {#if reminder.interval_days}
                      <span class="detail-meta">Every {reminder.interval_days} days</span>
                    {:else if reminder.next_date}
                      <span class="detail-meta">{formatDate(reminder.next_date)}</span>
                    {/if}
                  </li>
                {/each}
              </ul>
            </section>
          {/if}

          <!-- Interactions -->
          {#if selected.interactions.length > 0}
            <section class="card interactions-card">
              <h3>Interactions</h3>
              <ul>
                {#each selected.interactions.slice(0, 20) as ix}
                  <li>
                    <div class="ix-row">
                      <span class="ix-date">{formatDateTime(ix.date)}</span>
                      <span class="badge type-badge">{ix.type}</span>
                    </div>
                    {#if ix.notes}
                      <span class="detail-meta">{ix.notes}</span>
                    {/if}
                  </li>
                {/each}
              </ul>
            </section>
          {/if}
        </div>
        {:else}
        <div class="detail-hint">
          <p>No details saved yet</p>
          <small>Chat with homeclaw to add things like:</small>
          <ul>
            <li>Birthday and important dates</li>
            <li>Notes and facts</li>
            <li>Interaction history</li>
            <li>Recurring reminders to stay in touch</li>
          </ul>
        </div>
        {/if}
      {/if}
    </div>
  {:else}
    <!-- Contact list -->
    {#if filtered.length === 0}
      <div class="empty">
        <p>No contacts match "{search}"</p>
      </div>
    {:else}
      {#if members.length > 0}
        <h3 class="group-label">Household</h3>
        <div class="contact-list">
          {#each members as contact}
            {@render contactRow(contact)}
          {/each}
        </div>
      {/if}

      {#if others.length > 0}
        <h3 class="group-label">Contacts</h3>
        <div class="contact-list">
          {#each others as contact}
            {@render contactRow(contact)}
          {/each}
        </div>
      {/if}
    {/if}
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

  .loading-dot:nth-child(2) {
    animation-delay: 0.15s;
  }

  .loading-dot:nth-child(3) {
    animation-delay: 0.3s;
  }

  @keyframes pulse {
    0%,
    100% {
      opacity: 0.3;
      transform: scale(1);
    }
    50% {
      opacity: 1;
      transform: scale(1.2);
    }
  }

  /* ---- Error ---- */
  .error-card {
    background: #fef2f0;
    border-radius: var(--radius);
    padding: 1.5rem;
    text-align: center;
    color: var(--primary);
  }

  .error-card p {
    margin: 0 0 0.5rem;
    font-weight: 500;
  }

  .error-card small {
    color: var(--text-muted);
  }

  /* ---- Page header ---- */
  .page-header {
    margin-bottom: 1.5rem;
  }

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
  .search-bar {
    margin-bottom: 1rem;
  }

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

  .search-bar input:focus {
    border-color: var(--primary);
  }

  .search-bar input::placeholder {
    color: var(--text-muted);
  }

  /* ---- Group labels ---- */
  .group-label {
    font-family: var(--font-sans);
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 1.25rem 0 0.5rem;
  }

  .group-label:first-of-type {
    margin-top: 0;
  }

  /* ---- Contact list ---- */
  .contact-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    background: transparent;
    border-radius: var(--radius);
    overflow: hidden;
  }

  .contact-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    background: var(--surface);
    border-radius: var(--radius);
    cursor: pointer;
    text-align: left;
    font-family: inherit;
    text-decoration: none;
    color: inherit;
    transition: background 0.1s;
    width: 100%;
  }

  .contact-row:hover {
    background: var(--surface-low);
    box-shadow: inset 0 0 0 1px rgba(198, 200, 184, 0.2);
  }

  /* ---- Avatar ---- */
  .contact-avatar,
  .detail-avatar {
    flex-shrink: 0;
    width: 2.2rem;
    height: 2.2rem;
    border-radius: 50%;
    background: var(--primary);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.03em;
  }

  .member-avatar {
    background: var(--sage);
  }

  .detail-avatar {
    width: 3rem;
    height: 3rem;
    font-size: 0.9rem;
    background: var(--secondary);
  }

  /* ---- Contact info ---- */
  .contact-info {
    flex: 1;
    min-width: 0;
  }

  .contact-name {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text);
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .contact-meta {
    font-size: 0.78rem;
    color: var(--text-muted);
    margin-top: 0.1rem;
  }

  .contact-meta .sep {
    margin: 0 0.15rem;
  }

  .contact-arrow {
    color: var(--text-muted);
    font-size: 1.2rem;
    flex-shrink: 0;
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

  .member-badge {
    background: var(--surface-low);
    color: var(--sage);
  }

  .type-badge {
    background: var(--surface-low);
    color: var(--text-muted);
  }

  /* ---- Detail panel ---- */
  .back-btn {
    display: inline-block;
    color: var(--primary);
    font-family: inherit;
    font-size: 0.85rem;
    text-decoration: none;
    cursor: pointer;
    padding: 0;
    margin-bottom: 1rem;
  }

  .back-btn:hover {
    text-decoration: underline;
  }

  .detail-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  .detail-header h2 {
    font-family: var(--font-serif);
    font-size: 1.5rem;
    font-weight: 600;
    margin: 0;
    color: var(--text);
  }

  .detail-relationship {
    display: block;
    font-size: 0.85rem;
    color: var(--text-muted);
    text-transform: capitalize;
  }

  .detail-nicknames {
    display: block;
    font-size: 0.78rem;
    color: var(--text-muted);
    font-style: italic;
  }

  .detail-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
  }

  @media (max-width: 640px) {
    .detail-grid {
      grid-template-columns: 1fr;
    }
  }

  /* ---- Detail cards ---- */
  .card {
    background: var(--surface);
    border-radius: var(--radius);
    padding: 1rem 1.25rem;
  }

  .card h3 {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 0.92rem;
    color: var(--text);
    margin: 0 0 0.75rem;
  }

  .card ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .card li {
    padding: 0.5rem 0;
    font-size: 0.85rem;
    color: var(--text);
  }

  .card li:first-child {
    border-top: none;
    padding-top: 0;
  }

  .card li:last-child {
    padding-bottom: 0;
  }

  /* ---- Info card ---- */
  .info-card {
    grid-column: 1 / -1;
  }

  .info-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.4rem 0;
    font-size: 0.85rem;
  }

  .info-row + .info-row {
    margin-top: 0.2rem;
  }

  .info-label {
    color: var(--text-muted);
    font-size: 0.8rem;
  }

  /* ---- Interactions card ---- */
  .interactions-card {
    grid-column: 1 / -1;
  }

  .ix-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .ix-date {
    font-size: 0.78rem;
    color: var(--text-muted);
    min-width: 6rem;
  }

  .detail-meta {
    display: block;
    font-size: 0.78rem;
    color: var(--text-muted);
    margin-top: 0.1rem;
  }

  .reminder-note {
    font-weight: 500;
  }

  /* ---- Personal notes ---- */
  .personal-notes-card h3 {
    color: var(--sage);
  }

  /* ---- Contact notes ---- */
  .contact-notes {
    font-family: var(--font-sans);
    font-size: 0.84rem;
    line-height: 1.5;
    color: var(--text);
    margin: 0;
  }

  .contact-notes :global(p) { margin: 0 0 0.4rem; }
  .contact-notes :global(p:last-child) { margin-bottom: 0; }
  .contact-notes :global(ul), .contact-notes :global(ol) { margin: 0.2rem 0; padding-left: 1.2rem; }

  /* ---- Detail hint ---- */
  .detail-hint {
    text-align: center;
    padding: 2rem 1rem;
    color: var(--text-muted);
  }

  .detail-hint p {
    font-family: var(--font-serif);
    font-style: italic;
    font-size: 1rem;
    margin: 0 0 0.25rem;
  }

  .detail-hint small {
    font-size: 0.82rem;
  }

  .detail-hint ul {
    list-style: none;
    padding: 0;
    margin: 0.75rem 0 0;
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 0.4rem;
  }

  .detail-hint li {
    font-size: 0.78rem;
    background: var(--surface);
    padding: 0.3rem 0.6rem;
    border-radius: var(--radius-sm);
  }

  /* ---- Empty state ---- */
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
</style>

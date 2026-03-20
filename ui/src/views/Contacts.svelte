<script lang="ts">
  import { api } from "$lib/api";
  import { renderMarkdown } from "$lib/markdown";

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

  async function selectContact(id: string) {
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

  function closeDetail() {
    selected = null;
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
</script>

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
{:else}
  <header class="page-header" style="animation-delay: 0ms">
    <h1>Contacts</h1>
    <p class="subtitle">{contacts.length} {contacts.length === 1 ? "person" : "people"}</p>
  </header>

  <div class="search-bar" style="animation-delay: 60ms">
    <input
      type="text"
      placeholder="Search by name, nickname, or relationship..."
      bind:value={search}
    />
  </div>

  {#if selected}
    <!-- Detail panel -->
    <div class="detail-panel" style="animation-delay: 0ms">
      <button class="back-btn" onclick={closeDetail}>&larr; All contacts</button>

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

        <div class="detail-grid">
          <!-- Info card -->
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

          <!-- Notes -->
          {#if selected.notes_md}
            <section class="card">
              <h3>Notes</h3>
              <div class="contact-notes">{@html renderMarkdown(selected.notes_md)}</div>
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
      {/if}
    </div>
  {:else}
    <!-- Contact list -->
    {#if filtered.length === 0}
      <div class="empty" style="animation-delay: 120ms">
        {#if search.trim()}
          <p>No contacts match "{search}"</p>
        {:else}
          <p>No contacts yet</p>
          <small>Chat with homeclaw to start building your address book.</small>
        {/if}
      </div>
    {:else}
      <div class="contact-list">
        {#each filtered as contact, i}
          <button
            class="contact-row"
            style="animation-delay: {120 + i * 30}ms"
            onclick={() => selectContact(contact.id)}
          >
            <div class="contact-avatar">
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
                {#if contact.member}
                  <span class="badge member-badge">member</span>
                {/if}
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
          </button>
        {/each}
      </div>
    {/if}
  {/if}
{/if}

<style>
  /* ---- Entrance animation ---- */
  @keyframes fadeUp {
    from {
      opacity: 0;
      transform: translateY(12px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .page-header,
  .search-bar,
  .contact-row,
  .detail-panel,
  .empty {
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
    border: 1px solid #f0c4bc;
    border-radius: var(--radius);
    padding: 1.5rem;
    text-align: center;
    color: var(--terracotta);
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
    border-radius: var(--radius);
    background: var(--surface);
    font-family: var(--font-sans);
    font-size: 0.88rem;
    color: var(--text);
    outline: none;
    transition: border-color 0.15s;
    box-sizing: border-box;
  }

  .search-bar input:focus {
    border-color: var(--terracotta);
  }

  .search-bar input::placeholder {
    color: var(--text-muted);
  }

  /* ---- Contact list ---- */
  .contact-list {
    display: flex;
    flex-direction: column;
    gap: 1px;
    background: var(--border);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
  }

  .contact-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    background: var(--surface);
    border: none;
    cursor: pointer;
    text-align: left;
    font-family: inherit;
    transition: background 0.1s;
    width: 100%;
  }

  .contact-row:hover {
    background: #fdfcfa;
  }

  /* ---- Avatar ---- */
  .contact-avatar,
  .detail-avatar {
    flex-shrink: 0;
    width: 2.2rem;
    height: 2.2rem;
    border-radius: 50%;
    background: var(--sage);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.03em;
  }

  .detail-avatar {
    width: 3rem;
    height: 3rem;
    font-size: 0.9rem;
    background: var(--terracotta);
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
    border-radius: 4px;
    letter-spacing: 0.02em;
    text-transform: capitalize;
  }

  .member-badge {
    background: #eef4ef;
    color: var(--sage);
  }

  .type-badge {
    background: #f0ebe5;
    color: var(--text-muted);
  }

  /* ---- Detail panel ---- */
  .back-btn {
    background: none;
    border: none;
    color: var(--terracotta);
    font-family: inherit;
    font-size: 0.85rem;
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
    border: 1px solid var(--border);
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
    border-top: 1px solid var(--border);
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
    border-top: 1px solid var(--border);
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

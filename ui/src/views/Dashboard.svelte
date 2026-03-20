<script lang="ts">
  import { api } from "$lib/api";
  import { renderMarkdown } from "$lib/markdown";

  interface TodayNote {
    person: string;
    content: string;
    updated_at?: string;
  }
  interface Reminder {
    date: string;
    person: string;
    note: string;
  }
  interface Birthday {
    date: string;
    name: string;
    relationship: string;
  }
  interface Interaction {
    date: string;
    contact: string;
    type: string;
    notes: string;
  }
  interface OverdueCheckin {
    contact: string;
    relationship: string;
    note: string;
    due_date: string;
    days_overdue: number;
  }
  interface DashboardData {
    date: string;
    members: string[];
    today_notes: TodayNote[];
    upcoming_reminders: Reminder[];
    upcoming_birthdays: Birthday[];
    recent_interactions: Interaction[];
    overdue_checkins: OverdueCheckin[];
  }

  let data: DashboardData | null = $state(null);
  let error: string | null = $state(null);
  let loading: boolean = $state(true);

  const greeting = $derived.by(() => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 17) return "Good afternoon";
    return "Good evening";
  });

  const displayDate = $derived.by(() => {
    if (!data?.date) return "";
    const d = new Date(data.date + "T12:00:00");
    return d.toLocaleDateString("en-US", {
      weekday: "long",
      month: "long",
      day: "numeric",
    });
  });

  function formatDate(iso: string): string {
    const d = new Date(iso + "T12:00:00");
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    if (d.toDateString() === today.toDateString()) return "Today";
    if (d.toDateString() === tomorrow.toDateString()) return "Tomorrow";
    return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
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
    return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  }

  function daysUntil(iso: string): string {
    const d = new Date(iso + "T12:00:00");
    const now = new Date();
    const diff = Math.ceil((d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
    if (diff === 0) return "today";
    if (diff === 1) return "tomorrow";
    return `in ${diff} days`;
  }

  $effect(() => {
    api("/api/dashboard")
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((d: DashboardData) => {
        data = d;
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
    <p>Couldn't load the dashboard — is the API running?</p>
    <small>{error}</small>
  </div>
{:else if data}
  <header class="greeting" style="animation-delay: 0ms">
    <h1>{greeting}</h1>
    <p class="date">{displayDate}</p>
    {#if data.members.length > 0}
      <p class="members">
        {data.members.join(" · ")}
      </p>
    {/if}
  </header>

  <!-- Overdue check-ins — urgent, shown first -->
  {#if data.overdue_checkins.length > 0}
    <section class="card overdue" style="animation-delay: 60ms">
      <h2>Overdue check-ins</h2>
      <ul>
        {#each data.overdue_checkins as checkin}
          <li>
            <div class="overdue-row">
              <strong>{checkin.contact}</strong>
              <span class="badge overdue-badge">{checkin.days_overdue}d overdue</span>
            </div>
            <span class="detail">{checkin.note}</span>
          </li>
        {/each}
      </ul>
    </section>
  {/if}

  <div class="grid">
    <!-- Today's notes -->
    {#if data.today_notes.length > 0}
      <section class="card notes" style="animation-delay: 120ms">
        <h2>Today's notes</h2>
        {#each data.today_notes as note}
          <div class="note-block">
            <div class="note-header">
              <span class="note-person">{note.person}</span>
              {#if note.updated_at}
                <span class="note-time">updated {formatTime(note.updated_at)}</span>
              {/if}
            </div>
            <div class="note-content">{@html renderMarkdown(note.content)}</div>
          </div>
        {/each}
      </section>
    {/if}

    <!-- Upcoming reminders -->
    {#if data.upcoming_reminders.length > 0}
      <section class="card reminders" style="animation-delay: 180ms">
        <h2>Reminders</h2>
        <ul>
          {#each data.upcoming_reminders as reminder}
            <li>
              <span class="reminder-date">{formatDate(reminder.date)}</span>
              <span class="reminder-note">{reminder.note}</span>
              <span class="reminder-person">{reminder.person}</span>
            </li>
          {/each}
        </ul>
      </section>
    {/if}

    <!-- Upcoming birthdays -->
    {#if data.upcoming_birthdays.length > 0}
      <section class="card birthdays" style="animation-delay: 240ms">
        <h2>Birthdays coming up</h2>
        <ul>
          {#each data.upcoming_birthdays as bday}
            <li>
              <strong>{bday.name}</strong>
              <span class="detail">{bday.relationship} · {daysUntil(bday.date)}</span>
            </li>
          {/each}
        </ul>
      </section>
    {/if}

    <!-- Recent interactions -->
    {#if data.recent_interactions.length > 0}
      <section class="card interactions" style="animation-delay: 300ms">
        <h2>Recent interactions</h2>
        <ul>
          {#each data.recent_interactions.slice(0, 8) as ix}
            <li>
              <div class="ix-row">
                <strong>{ix.contact}</strong>
                <span class="badge type-badge">{ix.type}</span>
              </div>
              {#if ix.notes}
                <span class="detail">{ix.notes}</span>
              {/if}
            </li>
          {/each}
        </ul>
      </section>
    {/if}
  </div>

  <!-- Empty state -->
  {#if data.today_notes.length === 0 && data.upcoming_reminders.length === 0 && data.upcoming_birthdays.length === 0 && data.recent_interactions.length === 0 && data.overdue_checkins.length === 0}
    <div class="empty" style="animation-delay: 120ms">
      <p>Nothing on the board yet.</p>
      <small>Chat with homeclaw on Telegram to start building your household's story.</small>
    </div>
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

  .greeting,
  .card,
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

  /* ---- Greeting header ---- */
  .greeting {
    margin-bottom: 2rem;
  }

  .greeting h1 {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 2rem;
    margin: 0;
    color: var(--text);
    letter-spacing: -0.02em;
  }

  .greeting .date {
    font-size: 0.95rem;
    color: var(--text-muted);
    margin: 0.25rem 0 0;
  }

  .greeting .members {
    font-size: 0.8rem;
    color: var(--text-muted);
    margin: 0.5rem 0 0;
    text-transform: capitalize;
    letter-spacing: 0.02em;
  }

  /* ---- Card base ---- */
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.25rem 1.5rem;
  }

  .card h2 {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 1rem;
    color: var(--text);
    margin: 0 0 1rem;
    letter-spacing: -0.01em;
  }

  .card ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .card li {
    padding: 0.6rem 0;
    border-top: 1px solid var(--border);
    font-size: 0.88rem;
  }

  .card li:first-child {
    border-top: none;
    padding-top: 0;
  }

  .card li:last-child {
    padding-bottom: 0;
  }

  .card li strong {
    font-weight: 600;
    color: var(--text);
  }

  .detail {
    display: block;
    font-size: 0.82rem;
    color: var(--text-muted);
    margin-top: 0.15rem;
  }

  /* ---- Grid layout ---- */
  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
  }

  @media (max-width: 640px) {
    .grid {
      grid-template-columns: 1fr;
    }
  }

  /* ---- Notes ---- */
  .notes {
    grid-column: 1 / -1;
  }

  .note-block {
    padding: 0.75rem;
    background: #fdfcfa;
    border-radius: 8px;
    margin-bottom: 0.5rem;
    border-left: 3px solid var(--sage);
  }

  .note-block:last-child {
    margin-bottom: 0;
  }

  .note-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .note-person {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: capitalize;
    color: var(--sage);
    letter-spacing: 0.03em;
  }

  .note-time {
    font-size: 0.72rem;
    color: var(--text-muted);
  }

  .note-content {
    margin: 0.3rem 0 0;
    font-size: 0.88rem;
    line-height: 1.6;
    color: var(--text);
  }

  .note-content :global(p) {
    margin: 0.3rem 0;
  }

  .note-content :global(p:first-child) {
    margin-top: 0;
  }

  .note-content :global(p:last-child) {
    margin-bottom: 0;
  }

  .note-content :global(ul),
  .note-content :global(ol) {
    margin: 0.3rem 0;
    padding-left: 1.4rem;
  }

  .note-content :global(li) {
    padding: 0.1rem 0;
    border-top: none;
  }

  .note-content :global(strong) {
    font-weight: 600;
  }

  .note-content :global(code) {
    background: #f0ebe5;
    padding: 0.1rem 0.3rem;
    border-radius: 3px;
    font-size: 0.82rem;
  }

  .note-content :global(a) {
    color: var(--terracotta);
    text-decoration: underline;
    text-decoration-color: rgba(196, 101, 58, 0.3);
  }

  .note-content :global(h1),
  .note-content :global(h2),
  .note-content :global(h3) {
    font-family: var(--font-serif);
    font-size: 0.92rem;
    margin: 0.5rem 0 0.2rem;
  }

  /* ---- Reminders ---- */
  .reminder-date {
    display: inline-block;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--amber);
    min-width: 5.5rem;
  }

  .reminder-note {
    color: var(--text);
  }

  .reminder-person {
    display: block;
    font-size: 0.75rem;
    color: var(--text-muted);
    text-transform: capitalize;
    margin-top: 0.1rem;
  }

  /* ---- Badges ---- */
  .badge {
    display: inline-block;
    font-size: 0.7rem;
    font-weight: 600;
    padding: 0.15rem 0.45rem;
    border-radius: 4px;
    letter-spacing: 0.02em;
    text-transform: capitalize;
  }

  .type-badge {
    background: #f0ebe5;
    color: var(--text-muted);
  }

  .overdue-badge {
    background: #fef2f0;
    color: var(--terracotta);
  }

  /* ---- Overdue section ---- */
  .overdue {
    border-color: #f0c4bc;
    background: #fffbfa;
    margin-bottom: 1rem;
  }

  .overdue h2 {
    color: var(--terracotta);
  }

  .overdue-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  /* ---- Interactions ---- */
  .ix-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  /* ---- Birthdays ---- */
  .birthdays li strong::before {
    content: "🎂 ";
    font-size: 0.85rem;
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

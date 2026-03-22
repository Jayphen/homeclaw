<script lang="ts">
  import { api } from "$lib/api";
  import { renderMarkdown } from "$lib/markdown";
  import { formatRelativeTime as formatTime } from "$lib/time";

  // ---- Existing dashboard types ----
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

  // ---- Knowledge types ----
  interface TopicStat {
    name: string;
    entries: number;
    last_updated: string | null;
    size_bytes: number;
  }
  interface MemberKnowledge {
    person: string;
    topic_count: number;
    total_entries: number;
    topics: TopicStat[];
    earliest_entry: string | null;
    latest_entry: string | null;
  }
  interface KnowledgeData {
    summary: {
      total_topics: number;
      total_entries: number;
      total_contacts: number;
      total_notes: number;
      total_bookmarks: number;
      total_interactions: number;
      semantic_status: string;
    };
    members: MemberKnowledge[];
    household: MemberKnowledge;
    contacts: {
      total: number;
      with_birthday: number;
      with_reminders: number;
    };
  }

  // ---- Feed types ----
  interface FeedEvent {
    ts: string;
    type: string;
    summary: string;
    detail: string | null;
    person: string | null;
    meta: Record<string, string>;
  }
  interface FeedData {
    events: FeedEvent[];
    total: number;
    type_counts: Record<string, number>;
    since: string;
  }

  let data: DashboardData | null = $state(null);
  let knowledge: KnowledgeData | null = $state(null);
  let feed: FeedData | null = $state(null);
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

  function daysUntil(iso: string): string {
    const d = new Date(iso + "T12:00:00");
    const now = new Date();
    const diff = Math.ceil((d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
    if (diff === 0) return "today";
    if (diff === 1) return "tomorrow";
    return `in ${diff} days`;
  }

  const feedTypeLabels: Record<string, string> = {
    memory_save: "Memory",
    routine_run: "Routine",
    interaction: "Interaction",
    note_update: "Note",
    cost_spike: "Cost",
  };

  const feedTypeColors: Record<string, string> = {
    memory_save: "var(--sage)",
    routine_run: "var(--amber)",
    interaction: "var(--primary)",
    note_update: "var(--text-muted)",
    cost_spike: "var(--secondary)",
  };

  // Fetch all three endpoints in parallel
  $effect(() => {
    Promise.all([
      api("/api/dashboard").then((r) => {
        if (!r.ok) throw new Error(`Dashboard: ${r.status}`);
        return r.json();
      }),
      api("/api/knowledge").then((r) => {
        if (!r.ok) return null; // non-critical
        return r.json();
      }),
      api("/api/feed?days=3&limit=20").then((r) => {
        if (!r.ok) return null; // non-critical
        return r.json();
      }),
    ])
      .then(([d, k, f]: [DashboardData, KnowledgeData | null, FeedData | null]) => {
        data = d;
        knowledge = k;
        feed = f;
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
  <header class="greeting">
    <h1>{greeting}</h1>
    <p class="date">{displayDate}</p>
    {#if data.members.length > 0}
      <p class="members">
        {data.members.join(" · ")}
      </p>
    {/if}
  </header>

  <!-- ============ Knowledge Stats Bar ============ -->
  {#if knowledge}
    <section class="knowledge-bar">
      <div class="stat">
        <span class="stat-value">{knowledge.summary.total_entries}</span>
        <span class="stat-label">memories</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat">
        <span class="stat-value">{knowledge.summary.total_topics}</span>
        <span class="stat-label">topics</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat">
        <span class="stat-value">{knowledge.summary.total_contacts}</span>
        <span class="stat-label">contacts</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat">
        <span class="stat-value">{knowledge.summary.total_notes}</span>
        <span class="stat-label">notes</span>
      </div>
      {#if knowledge.summary.total_bookmarks > 0}
        <div class="stat-divider"></div>
        <div class="stat">
          <span class="stat-value">{knowledge.summary.total_bookmarks}</span>
          <span class="stat-label">bookmarks</span>
        </div>
      {/if}
    </section>

    <!-- Per-member knowledge breakdown -->
    {#if knowledge.household.topic_count > 0 || knowledge.members.some(m => m.topic_count > 0)}
      <section class="card knowledge-detail">
        <h2>What homeclaw knows</h2>
        <div class="knowledge-grid">
          {#if knowledge.household.topic_count > 0}
            <div class="knowledge-member">
              <div class="knowledge-member-header">
                <span class="knowledge-person">household</span>
                <span class="knowledge-count">{knowledge.household.total_entries} entries</span>
              </div>
              <div class="topic-pills">
                {#each knowledge.household.topics.slice(0, 8) as topic}
                  <span class="topic-pill" title="{topic.entries} entries">
                    {topic.name}
                    <span class="topic-count">{topic.entries}</span>
                  </span>
                {/each}
                {#if knowledge.household.topics.length > 8}
                  <span class="topic-pill more">+{knowledge.household.topics.length - 8} more</span>
                {/if}
              </div>
            </div>
          {/if}
          {#each knowledge.members as member}
            {#if member.topic_count > 0}
              <div class="knowledge-member">
                <div class="knowledge-member-header">
                  <span class="knowledge-person">{member.person}</span>
                  <span class="knowledge-count">{member.total_entries} entries</span>
                </div>
                <div class="topic-pills">
                  {#each member.topics.slice(0, 8) as topic}
                    <span class="topic-pill" title="{topic.entries} entries">
                      {topic.name}
                      <span class="topic-count">{topic.entries}</span>
                    </span>
                  {/each}
                  {#if member.topics.length > 8}
                    <span class="topic-pill more">+{member.topics.length - 8} more</span>
                  {/if}
                </div>
              </div>
            {/if}
          {/each}
        </div>
      </section>
    {/if}
  {/if}

  <!-- Overdue check-ins — urgent, shown first -->
  {#if data.overdue_checkins.length > 0}
    <section class="card overdue">
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
      <section class="card notes">
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
      <section class="card reminders">
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
      <section class="card birthdays">
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
      <section class="card interactions">
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

  <!-- ============ Activity Feed ============ -->
  {#if feed && feed.events.length > 0}
    <section class="card feed">
      <div class="feed-header">
        <h2>Recent activity</h2>
        <span class="feed-total">{feed.total} events</span>
      </div>
      <div class="feed-timeline">
        {#each feed.events as event}
          <div class="feed-event">
            <div class="feed-dot" style="background: {feedTypeColors[event.type] ?? 'var(--text-muted)'}"></div>
            <div class="feed-content">
              <div class="feed-event-header">
                <span class="feed-summary">{event.summary}</span>
                <span class="feed-time">{formatTime(event.ts)}</span>
              </div>
              {#if event.detail}
                <span class="feed-detail">{event.detail}</span>
              {/if}
              <div class="feed-meta">
                <span class="badge feed-type-badge" style="color: {feedTypeColors[event.type] ?? 'var(--text-muted)'}">
                  {feedTypeLabels[event.type] ?? event.type}
                </span>
                {#if event.person}
                  <span class="feed-person">{event.person}</span>
                {/if}
              </div>
            </div>
          </div>
        {/each}
      </div>
    </section>
  {/if}

  <!-- Empty state -->
  {#if data.today_notes.length === 0 && data.upcoming_reminders.length === 0 && data.upcoming_birthdays.length === 0 && data.recent_interactions.length === 0 && data.overdue_checkins.length === 0 && (!feed || feed.events.length === 0) && (!knowledge || knowledge.summary.total_entries === 0)}
    <div class="empty">
      <p>Nothing on the board yet.</p>
      <small>Chat with homeclaw on Telegram to start building your household's story.</small>
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
    color: var(--secondary);
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
    margin-bottom: 2.75rem;
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

  /* ---- Knowledge Stats Bar ---- */
  .knowledge-bar {
    display: flex;
    align-items: center;
    gap: 1.25rem;
    padding: 1rem 1.5rem;
    background: var(--surface);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    margin-bottom: 2rem;
    flex-wrap: wrap;
  }

  .stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.15rem;
  }

  .stat-value {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 1.5rem;
    color: var(--text);
    letter-spacing: -0.02em;
    line-height: 1;
  }

  .stat-label {
    font-size: 0.7rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .stat-divider {
    width: 1px;
    height: 1.5rem;
    background: var(--surface-low);
  }

  /* ---- Knowledge Detail Card ---- */
  .knowledge-detail {
    margin-bottom: 2rem;
  }

  .knowledge-grid {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .knowledge-member {
    padding: 0.75rem;
    background: var(--surface-low);
    border-radius: var(--radius-md);
  }

  .knowledge-member-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.5rem;
  }

  .knowledge-person {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: capitalize;
    color: var(--sage);
    letter-spacing: 0.03em;
  }

  .knowledge-count {
    font-size: 0.72rem;
    color: var(--text-muted);
  }

  .topic-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }

  .topic-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.72rem;
    padding: 0.2rem 0.5rem;
    background: var(--surface);
    border-radius: 100px;
    color: var(--text);
  }

  .topic-pill .topic-count {
    font-size: 0.65rem;
    color: var(--text-muted);
    font-weight: 600;
  }

  .topic-pill.more {
    color: var(--text-muted);
    font-style: italic;
  }

  /* ---- Card base ---- */
  .card {
    background: var(--surface);
    border-radius: var(--radius);
    padding: 1.5rem;
    box-shadow: var(--shadow);
    transition: background 0.2s, box-shadow 0.2s;
  }

  .card:hover {
    background: var(--surface-bright);
    box-shadow: 0 0 0 1px rgba(198, 200, 184, 0.2), var(--shadow);
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
    padding: 0.5rem 0.6rem;
    font-size: 0.88rem;
    border-radius: var(--radius-sm);
  }

  .card li:nth-child(even) {
    background: var(--surface-low);
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
    gap: 2rem;
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
    background: var(--surface-low);
    border-radius: var(--radius-md);
    margin-bottom: 0.5rem;
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
    background: var(--surface-low);
    padding: 0.1rem 0.3rem;
    border-radius: var(--radius-sm);
    font-size: 0.82rem;
  }

  .note-content :global(a) {
    color: var(--primary);
    text-decoration: underline;
    text-decoration-color: rgba(86, 100, 43, 0.3);
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
    border-radius: var(--radius-pill);
    letter-spacing: 0.02em;
    text-transform: capitalize;
  }

  .type-badge {
    background: var(--surface-low);
    color: var(--text-muted);
  }

  .overdue-badge {
    background: #fef2f0;
    color: var(--secondary);
  }

  /* ---- Overdue section ---- */
  .overdue {
    background: #fffbfa;
    margin-bottom: 2rem;
  }

  .overdue h2 {
    color: var(--secondary);
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

  /* ---- Activity Feed ---- */
  .feed {
    margin-top: 2rem;
  }

  .feed-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
  }

  .feed-header h2 {
    margin: 0;
  }

  .feed-total {
    font-size: 0.72rem;
    color: var(--text-muted);
  }

  .feed-timeline {
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .feed-event {
    display: flex;
    gap: 0.75rem;
    padding: 0.6rem 0.75rem;
    border-radius: var(--radius-sm);
  }

  .feed-event:nth-child(even) {
    background: var(--surface-low);
  }

  .feed-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-top: 0.35rem;
    flex-shrink: 0;
  }

  .feed-content {
    flex: 1;
    min-width: 0;
  }

  .feed-event-header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .feed-summary {
    font-size: 0.88rem;
    font-weight: 500;
    color: var(--text);
  }

  .feed-time {
    font-size: 0.72rem;
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .feed-detail {
    display: block;
    font-size: 0.8rem;
    color: var(--text-muted);
    margin-top: 0.15rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .feed-meta {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    margin-top: 0.25rem;
  }

  .feed-type-badge {
    background: var(--surface-low);
    font-size: 0.65rem;
    padding: 0.1rem 0.35rem;
  }

  .feed-person {
    font-size: 0.65rem;
    color: var(--text-muted);
    text-transform: capitalize;
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

<script lang="ts">
  import {
    format,
    parse,
    startOfMonth,
    endOfMonth,
    startOfWeek,
    endOfWeek,
    eachDayOfInterval,
    addMonths,
    addDays,
    subMonths,
    isSameMonth,
    isToday,
    isSameDay,
    parseISO,
  } from "date-fns";
  import { querystring } from "svelte-spa-router";
  import { api } from "$lib/api";
  import { renderMarkdown } from "$lib/markdown";

  type ViewMode = "month" | "schedule";

  interface CalendarEvent {
    date: string;
    type: "note" | "reminder" | "birthday" | "interaction";
    person: string;
    summary: string;
    done?: boolean;
  }

  interface CalendarData {
    month: string;
    event_count: number;
    events: CalendarEvent[];
  }

  const TYPE_COLORS: Record<string, string> = {
    note: "var(--sage)",
    reminder: "var(--amber)",
    birthday: "var(--rose)",
    interaction: "var(--terracotta)",
  };

  const TYPE_LABELS: Record<string, string> = {
    note: "Note",
    reminder: "Reminder",
    birthday: "Birthday",
    interaction: "Interaction",
  };

  const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const SCHEDULE_DAYS = 7;

  // Parse ?date=YYYY-MM-DD from URL for deep linking
  function initFromQuery(): { initDate: Date; initSelected: Date | null } {
    const qs = $querystring;
    if (qs) {
      const params = new URLSearchParams(qs);
      const dateParam = params.get("date");
      if (dateParam) {
        try {
          const d = parseISO(dateParam);
          if (!isNaN(d.getTime())) return { initDate: d, initSelected: d };
        } catch { /* ignore */ }
      }
    }
    return { initDate: new Date(), initSelected: null };
  }

  const { initDate, initSelected } = initFromQuery();

  let view: ViewMode = $state("month");
  let currentDate: Date = $state(initDate);
  let data: CalendarData | null = $state(null);
  let scheduleData: CalendarEvent[] = $state([]);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);
  let selectedDate: Date | null = $state(initSelected);

  const currentMonthStr = $derived(format(currentDate, "yyyy-MM"));
  const monthLabel = $derived(format(currentDate, "MMMM yyyy"));

  const calendarDays = $derived.by(() => {
    const monthStart = startOfMonth(currentDate);
    const monthEnd = endOfMonth(currentDate);
    const gridStart = startOfWeek(monthStart, { weekStartsOn: 1 });
    const gridEnd = endOfWeek(monthEnd, { weekStartsOn: 1 });

    return eachDayOfInterval({ start: gridStart, end: gridEnd }).map((day) => ({
      date: format(day, "yyyy-MM-dd"),
      day: day.getDate(),
      inMonth: isSameMonth(day, currentDate),
      ref: day,
    }));
  });

  const eventsByDate = $derived.by(() => {
    const map = new Map<string, CalendarEvent[]>();
    const events = view === "schedule" ? scheduleData : (data?.events || []);
    for (const ev of events) {
      const arr = map.get(ev.date) || [];
      arr.push(ev);
      map.set(ev.date, arr);
    }
    return map;
  });

  const selectedEvents = $derived.by(() => {
    if (!selectedDate) return [];
    const key = format(selectedDate, "yyyy-MM-dd");
    return eventsByDate.get(key) || [];
  });

  const scheduleDays = $derived.by(() => {
    const today = new Date();
    const end = addDays(today, SCHEDULE_DAYS - 1);
    return eachDayOfInterval({ start: today, end }).map((day) => ({
      date: format(day, "yyyy-MM-dd"),
      ref: day,
      label: isToday(day) ? "Today" : format(day, "EEE"),
      fullLabel: format(day, "EEEE, MMMM d"),
      dayNum: format(day, "d"),
      month: format(day, "MMM"),
    }));
  });

  function navigate(delta: number) {
    currentDate = delta > 0 ? addMonths(currentDate, delta) : subMonths(currentDate, -delta);
    selectedDate = null;
  }

  function goToday() {
    const today = new Date();
    currentDate = today;
    selectedDate = today;
    history.replaceState(null, "", `#/calendar?date=${format(today, "yyyy-MM-dd")}`);
  }

  function selectDay(day: Date) {
    if (selectedDate && isSameDay(selectedDate, day)) {
      selectedDate = null;
      history.replaceState(null, "", "#/calendar");
    } else {
      selectedDate = day;
      history.replaceState(null, "", `#/calendar?date=${format(day, "yyyy-MM-dd")}`);
    }
  }

  function formatSelectedDate(d: Date): string {
    return format(d, "EEEE, MMMM d");
  }

  function fetchMonth(month: string) {
    loading = true;
    error = null;
    api(`/api/calendar?month=${month}`)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((d: CalendarData) => {
        data = d;
        loading = false;
      })
      .catch((e) => {
        error = e.message;
        loading = false;
      });
  }

  async function fetchSchedule() {
    loading = true;
    error = null;
    try {
      const today = new Date();
      const endDate = addDays(today, SCHEDULE_DAYS - 1);
      const thisMonth = format(today, "yyyy-MM");
      const endMonth = format(endDate, "yyyy-MM");

      const months = [thisMonth];
      if (endMonth !== thisMonth) months.push(endMonth);

      const results = await Promise.all(
        months.map((m) =>
          api(`/api/calendar?month=${m}`).then((r) => {
            if (!r.ok) throw new Error(`${r.status}`);
            return r.json() as Promise<CalendarData>;
          }),
        ),
      );

      const todayStr = format(today, "yyyy-MM-dd");
      const endStr = format(endDate, "yyyy-MM-dd");
      const allEvents = results.flatMap((r) => r.events);
      scheduleData = allEvents
        .filter((ev) => ev.date >= todayStr && ev.date <= endStr)
        .sort((a, b) => a.date.localeCompare(b.date));
      loading = false;
    } catch (e: any) {
      error = e.message;
      loading = false;
    }
  }

  $effect(() => {
    if (view === "month") {
      fetchMonth(currentMonthStr);
    } else {
      fetchSchedule();
    }
  });
</script>

<div class="calendar-page">
  <header class="cal-header">
    {#if view === "month"}
      <h1>{monthLabel}</h1>
    {:else}
      <h1>Next 7 days</h1>
    {/if}
    <div class="nav-controls">
      <div class="view-toggle">
        <button
          class="toggle-btn"
          class:active={view === "schedule"}
          onclick={() => { view = "schedule"; selectedDate = null; }}
        >Schedule</button>
        <button
          class="toggle-btn"
          class:active={view === "month"}
          onclick={() => { view = "month"; selectedDate = null; }}
        >Month</button>
      </div>
      {#if view === "month"}
        <button class="nav-btn" onclick={() => navigate(-1)} aria-label="Previous month">
          ‹
        </button>
        <button class="today-btn" onclick={goToday}>Today</button>
        <button class="nav-btn" onclick={() => navigate(1)} aria-label="Next month">
          ›
        </button>
      {/if}
    </div>
  </header>

  <div class="legend">
    {#each Object.entries(TYPE_LABELS) as [type, label]}
      <span class="legend-item">
        <span class="legend-dot" style="background: {TYPE_COLORS[type]}"></span>
        {label}
      </span>
    {/each}
  </div>

  {#if loading}
    <div class="loading">
      <div class="loading-dot"></div>
      <div class="loading-dot"></div>
      <div class="loading-dot"></div>
    </div>
  {:else if error}
    <div class="error-card">
      <p>Couldn't load the calendar.</p>
      <small>{error}</small>
    </div>
  {:else if view === "month"}
    <div class="grid">
      {#each WEEKDAYS as day}
        <div class="weekday-header">{day}</div>
      {/each}

      {#each calendarDays as cell}
        {@const events = eventsByDate.get(cell.date) || []}
        {@const dayIsToday = isToday(cell.ref)}
        {@const isSelected = selectedDate != null && isSameDay(selectedDate, cell.ref)}
        <button
          class="day-cell"
          class:out-of-month={!cell.inMonth}
          class:today={dayIsToday}
          class:selected={isSelected}
          class:has-events={events.length > 0}
          onclick={() => selectDay(cell.ref)}
        >
          <span class="day-number">{cell.day}</span>
          {#if events.length > 0}
            <div class="event-dots">
              {#each events.slice(0, 4) as ev}
                <span
                  class="dot"
                  style="background: {TYPE_COLORS[ev.type]}"
                  title="{TYPE_LABELS[ev.type]}: {ev.summary.slice(0, 40)}"
                ></span>
              {/each}
              {#if events.length > 4}
                <span class="dot-overflow">+{events.length - 4}</span>
              {/if}
            </div>
          {/if}
        </button>
      {/each}
    </div>

    <!-- Detail drawer -->
    {#if selectedDate != null && selectedEvents.length > 0}
      <div class="detail-drawer">
        <h2>{formatSelectedDate(selectedDate)}</h2>
        <ul>
          {#each selectedEvents as ev}
            <li class:done={ev.done}>
              <span class="ev-type-dot" style="background: {TYPE_COLORS[ev.type]}"></span>
              <div class="ev-content">
                <div class="ev-header">
                  <span class="ev-type">{TYPE_LABELS[ev.type]}</span>
                  <span class="ev-person">{ev.person}</span>
                  {#if ev.type === "note"}
                    <a class="ev-link" href="#/notes/{ev.person}/{ev.date}">View note</a>
                  {/if}
                </div>
                <div class="ev-summary">{@html renderMarkdown(ev.summary)}</div>
              </div>
            </li>
          {/each}
        </ul>
      </div>
    {:else if selectedDate != null}
      <div class="detail-drawer empty-day">
        <h2>{formatSelectedDate(selectedDate)}</h2>
        <p class="nothing">Nothing on this day.</p>
      </div>
    {/if}
  {:else}
    <!-- Schedule view -->
    <div class="schedule">
      {#each scheduleDays as day}
        {@const events = eventsByDate.get(day.date) || []}
        {@const dayIsToday = isToday(day.ref)}
        <div class="schedule-day" class:schedule-today={dayIsToday}>
          <div class="schedule-date">
            <span class="schedule-daynum">{day.dayNum}</span>
            <div class="schedule-meta">
              <span class="schedule-weekday">{day.label}</span>
              <span class="schedule-month">{day.month}</span>
            </div>
          </div>
          <div class="schedule-events">
            {#if events.length > 0}
              {#each events as ev}
                <div class="schedule-event" class:done={ev.done}>
                  <span class="ev-type-dot" style="background: {TYPE_COLORS[ev.type]}"></span>
                  <div class="ev-content">
                    <div class="ev-header">
                      <span class="ev-type">{TYPE_LABELS[ev.type]}</span>
                      <span class="ev-person">{ev.person}</span>
                      {#if ev.type === "note"}
                        <a class="ev-link" href="#/notes/{ev.person}/{ev.date}">View note</a>
                      {/if}
                    </div>
                    <div class="ev-summary">{@html renderMarkdown(ev.summary)}</div>
                  </div>
                </div>
              {/each}
            {:else}
              <p class="schedule-empty">No events</p>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .calendar-page {
    animation: fadeUp 0.35s ease-out;
  }

  /* ---- Header ---- */
  .cal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
  }

  .cal-header h1 {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 1.6rem;
    margin: 0;
    letter-spacing: -0.02em;
    color: var(--text);
  }

  .nav-controls {
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }

  .nav-btn {
    width: 2rem;
    height: 2rem;
    border: none;
    border-radius: var(--radius-sm);
    background: var(--surface-low);
    color: var(--text);
    font-size: 1.1rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.15s;
  }

  .nav-btn:hover {
    background: var(--surface-low);
  }

  .today-btn {
    height: 2rem;
    padding: 0 0.75rem;
    border: none;
    border-radius: var(--radius-sm);
    background: var(--surface-low);
    color: var(--text-muted);
    font-family: var(--font-sans);
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }

  .today-btn:hover {
    background: var(--surface-low);
    color: var(--text);
  }

  /* ---- Legend ---- */
  .legend {
    display: flex;
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .legend-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }

  /* ---- Grid ---- */
  .grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    border-radius: var(--radius);
    overflow: hidden;
    background: var(--surface-low);
    gap: 2px;
  }

  .weekday-header {
    background: var(--surface-low);
    padding: 0.5rem;
    text-align: center;
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  /* ---- Day cells ---- */
  .day-cell {
    background: var(--surface);
    border: none;
    padding: 0.4rem;
    min-height: 4.5rem;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.25rem;
    text-align: left;
    font-family: var(--font-sans);
    transition: background 0.12s;
  }

  .day-cell:hover {
    background: var(--surface-low);
  }

  .day-cell.out-of-month {
    background: var(--bg);
  }

  .day-cell.out-of-month .day-number {
    color: #ccc5bc;
  }

  .day-cell.today {
    background: var(--surface-low);
  }

  .day-cell.today .day-number {
    background: var(--secondary);
    color: #fff;
    width: 1.5rem;
    height: 1.5rem;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .day-cell.selected {
    background: var(--surface-low);
    box-shadow: inset 0 0 0 2px var(--primary);
  }

  .day-number {
    font-size: 0.8rem;
    font-weight: 500;
    color: var(--text);
    line-height: 1;
  }

  /* ---- Event dots ---- */
  .event-dots {
    display: flex;
    flex-wrap: wrap;
    gap: 3px;
    margin-top: auto;
  }

  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .dot-overflow {
    font-size: 0.6rem;
    color: var(--text-muted);
    line-height: 7px;
  }

  /* ---- Detail drawer ---- */
  .detail-drawer {
    margin-top: 1rem;
    background: var(--surface);
    border-radius: var(--radius);
    padding: 1.25rem 1.5rem;
    animation: fadeUp 0.25s ease-out;
  }

  .detail-drawer h2 {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 1rem;
    margin: 0 0 0.75rem;
    color: var(--text);
  }

  .detail-drawer ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .detail-drawer li {
    display: flex;
    gap: 0.75rem;
    padding: 0.6rem 0;
    align-items: flex-start;
  }

  .detail-drawer li:first-child {
    border-top: none;
    padding-top: 0;
  }

  .detail-drawer li.done {
    opacity: 0.5;
  }

  .detail-drawer li.done .ev-summary {
    text-decoration: line-through;
  }

  .ev-type-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
    margin-top: 0.35rem;
  }

  .ev-content {
    flex: 1;
    min-width: 0;
  }

  .ev-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.15rem;
  }

  .ev-type {
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-muted);
  }

  .ev-person {
    font-size: 0.72rem;
    color: var(--text-muted);
    text-transform: capitalize;
  }

  .ev-link {
    margin-left: auto;
    font-size: 0.72rem;
    color: var(--primary);
    text-decoration: none;
  }

  .ev-link:hover {
    text-decoration: underline;
  }

  .ev-summary {
    margin: 0;
    font-size: 0.85rem;
    line-height: 1.4;
    color: var(--text);
  }

  .ev-summary :global(p) {
    margin: 0 0 0.3rem;
  }

  .ev-summary :global(p:last-child) {
    margin-bottom: 0;
  }

  .ev-summary :global(ul),
  .ev-summary :global(ol) {
    margin: 0.2rem 0;
    padding-left: 1.2rem;
  }

  .ev-summary :global(h1),
  .ev-summary :global(h2),
  .ev-summary :global(h3) {
    font-size: 0.9rem;
    font-weight: 600;
    margin: 0 0 0.2rem;
  }

  .empty-day .nothing {
    font-family: var(--font-serif);
    font-style: italic;
    color: var(--text-muted);
    font-size: 0.9rem;
    margin: 0;
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
    border-radius: var(--radius);
    padding: 1.5rem;
    text-align: center;
    color: var(--secondary);
  }

  .error-card p { margin: 0 0 0.5rem; font-weight: 500; }
  .error-card small { color: var(--text-muted); }

  /* ---- View toggle ---- */
  .view-toggle {
    display: flex;
    border-radius: var(--radius-pill);
    overflow: hidden;
    margin-right: 0.5rem;
    background: var(--surface-low);
  }

  .toggle-btn {
    padding: 0.3rem 0.6rem;
    border: none;
    background: var(--surface);
    color: var(--text-muted);
    font-family: var(--font-sans);
    font-size: 0.78rem;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }

  .toggle-btn.active {
    background: var(--primary);
    color: #fff;
  }

  .toggle-btn:not(.active):hover {
    background: var(--surface-low);
  }

  /* ---- Schedule view ---- */
  .schedule {
    display: flex;
    flex-direction: column;
    gap: 2px;
    background: var(--surface-low);
    border-radius: var(--radius);
    overflow: hidden;
  }

  .schedule-day {
    display: flex;
    gap: 1rem;
    padding: 0.75rem 1rem;
    background: var(--surface);
    min-height: 3rem;
  }

  .schedule-day.schedule-today {
    background: var(--surface-low);
  }

  .schedule-date {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    min-width: 5rem;
    flex-shrink: 0;
  }

  .schedule-daynum {
    font-family: var(--font-serif);
    font-size: 1.4rem;
    font-weight: 600;
    color: var(--text);
    line-height: 1;
    min-width: 1.8rem;
    text-align: right;
  }

  .schedule-today .schedule-daynum {
    color: var(--primary);
  }

  .schedule-meta {
    display: flex;
    flex-direction: column;
  }

  .schedule-weekday {
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--text);
  }

  .schedule-today .schedule-weekday {
    color: var(--primary);
  }

  .schedule-month {
    font-size: 0.7rem;
    color: var(--text-muted);
  }

  .schedule-events {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    justify-content: center;
  }

  .schedule-event {
    display: flex;
    gap: 0.6rem;
    align-items: flex-start;
  }

  .schedule-event.done {
    opacity: 0.5;
  }

  .schedule-event.done .ev-summary {
    text-decoration: line-through;
  }

  .schedule-empty {
    margin: 0;
    font-size: 0.8rem;
    color: var(--text-muted);
    font-style: italic;
  }

  /* ---- Responsive ---- */
  @media (max-width: 640px) {
    .day-cell {
      min-height: 3.5rem;
      padding: 0.3rem;
    }

    .day-number {
      font-size: 0.72rem;
    }

    .dot {
      width: 5px;
      height: 5px;
    }

    .legend {
      flex-wrap: wrap;
      gap: 0.5rem;
    }
  }
</style>

# homeclaw — LLM Cost Management Prompt

> Use this prompt with Claude Code in the homeclaw project directory.
> Run `bd quickstart` first. All work goes into beads.

---

You are implementing LLM cost management for **homeclaw**, an open source AI
household assistant written in Python. The project already has a working agent
loop and provider abstraction layer. This session adds cost controls that will
make the hosted tier economically viable without degrading the user experience.

Use `bd` for ALL task tracking. No markdown TODO files.

---

## Context: why this matters

homeclaw runs continuously — scheduled routines fire every few hours, every
conversation injects household context, memory and contacts are always present.
Unlike a chatbot that only costs money when users type, homeclaw incurs costs
even when the household is asleep. Without cost controls, the hosted tier unit
economics don't work at a $10-15/month subscription price.

The target: **$1-3/month API cost per household** on the hosted tier, down from
an estimated $3-8/month with a naive single-model approach.

During development, OpenRouter is the recommended provider — one API key, easy
model switching, negligible 5.5% fee at dev volumes. For the hosted tier at
scale, direct provider APIs (Anthropic, OpenAI) will be used to access prompt
caching fully and avoid the per-call overhead.

---

## What needs to exist after this session

### 1. Per-call model routing (`homeclaw/agent/routing.py`)

A `RoutingConfig` Pydantic model and a `route_model()` function that selects
the appropriate model for each call type. The agent loop currently uses one
global model for everything — this replaces that with intent-aware routing.

```python
# homeclaw/agent/routing.py
from enum import Enum
from pydantic import BaseModel

class CallType(Enum):
    CONVERSATION = "conversation"     # user sent a message, needs reasoning
    ROUTINE = "routine"               # scheduled heartbeat task
    TOOL_ONLY = "tool_only"           # simple tool call, no reasoning needed
    MEMORY_WRITE = "memory_write"     # saving a fact or note

class RoutingConfig(BaseModel):
    # Primary: used for conversations requiring reasoning
    conversation_model: str = "anthropic/claude-sonnet-4-6"

    # Cheap: used for scheduled routines and simple tool calls
    routine_model: str = "anthropic/claude-haiku-4-5-20251001"

    # Whether to use OpenRouter (dev) or direct providers (hosted)
    use_openrouter: bool = True
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Cost controls
    max_output_tokens: int = 1024     # prevents runaway verbose responses
    routine_max_output_tokens: int = 512

def route_model(call_type: CallType, config: RoutingConfig) -> str:
    if call_type in (CallType.ROUTINE, CallType.TOOL_ONLY, CallType.MEMORY_WRITE):
        return config.routine_model
    return config.conversation_model
```

Add `RoutingConfig` as a field on `HearthConfig`. Default values must work
out of the box — no required fields added.

The agent loop calls `route_model()` before every LLM call, passing the call
type. The scheduler always passes `CallType.ROUTINE`. The Telegram channel
adapter always passes `CallType.CONVERSATION`. The `memory_update` tool
internally uses `CallType.MEMORY_WRITE` when it triggers its own LLM call
(if it does — check if this applies).

---

### 2. Anthropic prompt caching (`homeclaw/agent/providers/anthropic.py`)

The household system prompt and context builder output repeat on almost every
call. Caching them gives up to 90% discount on those tokens with Anthropic's
API. This is the single highest-impact cost reduction available.

Cache the following at `cache_control` breakpoints:
- The static system prompt (household description, tool list, behaviour rules)
- The household context prefix (facts, contacts, HA state) — this changes
  slowly and benefits from caching even with a 5-minute TTL

Implementation requirements:
- Only applies when using Anthropic directly (not via OpenRouter, which may
  strip cache headers — check and document this behaviour)
- Add a config flag `enable_prompt_caching: bool = True` to `RoutingConfig`
- The Anthropic provider implementation must insert `cache_control` breakpoints
  at the correct positions in the messages array
- Log cache hit/miss in debug mode so cost savings are visible during testing

Anthropic caching specifics:
- Write cost: 25% higher than standard input (one-time)
- Read cost: 90% cheaper than standard input
- Cache TTL: 5 minutes, extended on hit
- Minimum cacheable size: 1024 tokens

---

### 3. Batch API for scheduled routines (`homeclaw/scheduler/batch.py`)

Scheduled routines — plant checks, contact reminders, daily summaries — do
not need to respond in real time. Running them through Anthropic's Message
Batches API gives a 50% discount on all tokens.

```python
# homeclaw/scheduler/batch.py

class BatchScheduler:
    """
    Accumulates routine LLM calls and submits them as a batch.
    Polls for results and dispatches responses via message_send tool.
    Falls back to real-time calls if batch results take > 30 minutes.
    """
    async def submit_routine(self, routine: RoutineRun) -> str:
        # Returns a batch_id for polling
        ...

    async def poll_and_dispatch(self) -> None:
        # Called every 5 minutes by the main scheduler
        # Dispatches completed routine results via message_send
        ...
```

Config flag: `enable_batch_routines: bool = True` on `RoutingConfig`.
When disabled, routines run as normal real-time calls (useful for development
and for providers that don't support batching).

Note: Batch API is Anthropic-specific. When using OpenRouter or other
providers, `enable_batch_routines` must be silently ignored and routines
run in real-time. Add a warning log when batch is configured but unavailable.

---

### 4. Context token budget (`homeclaw/agent/context.py`)

The context builder currently injects everything it knows. Add a hard token
budget to prevent runaway context costs on households with large contact lists,
long note histories, or many HA entities.

```python
class ContextConfig(BaseModel):
    max_context_tokens: int = 2000    # budget for injected context
    max_facts_per_person: int = 20    # cap facts injected from memory.json
    max_contacts_in_context: int = 5  # max contacts shown as due/upcoming
    max_semantic_chunks: int = 3      # memsearch top-k (already set, verify)
    max_ha_entities: int = 20         # HA entity states injected
```

Priority order when over budget (drop lowest priority first):
1. Always keep: current time, requesting person's facts, today's events
2. Drop first: HA entities beyond top 10 most recently changed
3. Drop second: semantic memory chunks beyond top 2
4. Drop third: contacts beyond top 3 most urgent
5. Never drop: active reminders due today

Add `ContextConfig` as a field on `HearthConfig`.

Measure and log the actual token count of the built context in debug mode.
Use `anthropic.count_tokens()` or a tiktoken equivalent — do not estimate.

---

### 5. Cost tracking (`homeclaw/agent/cost_tracker.py`)

A lightweight cost tracker that logs token usage per call to a rolling JSONL
file. Not a database — just appended log entries the web UI can read.

```python
# workspaces/cost_log.jsonl — one entry per LLM call
{
  "ts": "2026-03-16T09:23:11Z",
  "call_type": "conversation",
  "model": "claude-sonnet-4-6",
  "input_tokens": 1842,
  "output_tokens": 203,
  "cached_tokens": 1200,
  "estimated_cost_usd": 0.000412,
  "person": "alice"
}
```

Estimated cost is calculated using hardcoded price constants per model
(updated as a config file, not in code). Include a `prices.json` in the repo:

```json
{
  "claude-sonnet-4-6": {
    "input_per_mtok": 3.00,
    "output_per_mtok": 15.00,
    "cached_input_per_mtok": 0.30
  },
  "claude-haiku-4-5-20251001": {
    "input_per_mtok": 0.80,
    "output_per_mtok": 4.00,
    "cached_input_per_mtok": 0.08
  }
}
```

Rolling window: keep last 30 days of entries, prune older ones on startup.

---

### 6. Cost summary API endpoint (`homeclaw/api/routes/cost.py`)

A single read-only endpoint for the web UI:

```
GET /api/cost/summary?days=7
```

Response:
```json
{
  "period_days": 7,
  "total_cost_usd": 0.84,
  "projected_monthly_usd": 3.60,
  "by_model": {
    "claude-sonnet-4-6": {"calls": 47, "cost_usd": 0.71},
    "claude-haiku-4-5-20251001": {"calls": 89, "cost_usd": 0.13}
  },
  "by_call_type": {
    "conversation": {"calls": 47, "cost_usd": 0.71},
    "routine": {"calls": 89, "cost_usd": 0.13}
  },
  "cache_hit_rate": 0.64,
  "estimated_savings_from_routing_usd": 0.38,
  "estimated_savings_from_caching_usd": 0.21
}
```

Add a cost summary card to the web UI dashboard — projected monthly cost,
cache hit rate, and a simple bar showing cost by model. Keep it small, not a
prominent feature, but visible enough that the developer can monitor costs
during dogfooding.

---

### 7. `make dev-costs` target

Add to Makefile:

```makefile
# Print cost summary for the last 7 days from dev workspaces
dev-costs:
	python -c "
import json, datetime
from pathlib import Path
log = Path('workspaces-dev/cost_log.jsonl')
if not log.exists():
    print('No cost log yet.')
else:
    entries = [json.loads(l) for l in log.read_text().splitlines() if l]
    total = sum(e.get('estimated_cost_usd', 0) for e in entries)
    print(f'Total logged cost: \$${total:.4f} ({len(entries)} calls)')
"
```

---

## What NOT to do in this session

- Do not change the provider abstraction interface (`LLMProvider` Protocol)
- Do not add any required config fields — all new fields must have defaults
- Do not implement caching for OpenRouter calls — document why in a comment
- Do not add a billing or payment system — cost tracking is observability only
- Do not break existing tests — routing must be transparent to the test suite
  (the mock provider fixture bypasses routing entirely, this is correct)

---

## Your task

1. Run `bd quickstart`
2. Examine the current agent loop, provider implementations, scheduler, config,
   and context builder before creating any issues — understand what exists
3. Create beads issues for every item above. Key issues:
   - `RoutingConfig` model + `route_model()` function
   - Agent loop updated to call `route_model()` before each LLM call
   - Scheduler passes `CallType.ROUTINE` to all routine invocations
   - Anthropic provider: prompt caching with `cache_control` breakpoints
   - Verify whether OpenRouter strips `cache_control` headers (research + document)
   - `BatchScheduler` for routines (Anthropic only, graceful fallback)
   - `ContextConfig` with token budget enforcement
   - Token counting integrated into context builder
   - `CostTracker` with JSONL log + `prices.json`
   - `/api/cost/summary` endpoint
   - Dashboard cost card (Svelte component)
   - `make dev-costs` Makefile target
   - Update `workspaces-dev/` fixture to generate some cost log entries
   - Update `docs/DEVELOPMENT.md` with cost monitoring section
4. Set dependencies:
   - `RoutingConfig` blocks agent loop routing changes
   - Agent loop routing blocks scheduler `CallType` integration
   - `ContextConfig` blocks context builder token budget
   - Token counting blocks `CostTracker`
   - `CostTracker` blocks API endpoint
   - API endpoint blocks dashboard card
   - Anthropic caching is independent — can be done in parallel with routing
   - Batch scheduler depends on routing (needs to know call type)
5. After creating issues, run `bd ready --json`
6. Recommend what to tackle first and what "land the plane" looks like

**Do not write any code yet. Planning and issue creation only.**

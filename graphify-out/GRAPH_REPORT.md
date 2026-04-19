# Graph Report - .  (2026-04-19)

## Corpus Check
- Large corpus: 214 files · ~141,727 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 2602 nodes · 7079 edges · 92 communities detected
- Extraction: 46% EXTRACTED · 54% INFERRED · 0% AMBIGUOUS · INFERRED: 3853 edges (avg confidence: 0.62)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Auth & API Layer|Auth & API Layer]]
- [[_COMMUNITY_Plugin & Tool Registry|Plugin & Tool Registry]]
- [[_COMMUNITY_LLM Provider & Caching|LLM Provider & Caching]]
- [[_COMMUNITY_App Bootstrap & Config|App Bootstrap & Config]]
- [[_COMMUNITY_Web UI State & Auth|Web UI State & Auth]]
- [[_COMMUNITY_Skill Loader & Tools|Skill Loader & Tools]]
- [[_COMMUNITY_Scheduler & Routines|Scheduler & Routines]]
- [[_COMMUNITY_Plugin Marketplace|Plugin Marketplace]]
- [[_COMMUNITY_Calendar & Events|Calendar & Events]]
- [[_COMMUNITY_Marketplace Client|Marketplace Client]]
- [[_COMMUNITY_Configuration System|Configuration System]]
- [[_COMMUNITY_Memory & Semantic Search|Memory & Semantic Search]]
- [[_COMMUNITY_Telegram Adapter|Telegram Adapter]]
- [[_COMMUNITY_HTTP Tool & Safety|HTTP Tool & Safety]]
- [[_COMMUNITY_Tool Schema Generation|Tool Schema Generation]]
- [[_COMMUNITY_Household Members Data|Household Members Data]]
- [[_COMMUNITY_Plants Plugin|Plants Plugin]]
- [[_COMMUNITY_Bookmarks & Notes|Bookmarks & Notes]]
- [[_COMMUNITY_Skill Dependency Check|Skill Dependency Check]]
- [[_COMMUNITY_Cost Tracking|Cost Tracking]]
- [[_COMMUNITY_Tool Use Logging|Tool Use Logging]]
- [[_COMMUNITY_Core Architecture Concepts|Core Architecture Concepts]]
- [[_COMMUNITY_Path Safety Utilities|Path Safety Utilities]]
- [[_COMMUNITY_Log Buffer|Log Buffer]]
- [[_COMMUNITY_Data Export & Import|Data Export & Import]]
- [[_COMMUNITY_Terminal REPL|Terminal REPL]]
- [[_COMMUNITY_Dev Fixture Household|Dev Fixture Household]]
- [[_COMMUNITY_Dev Fixtures Setup|Dev Fixtures Setup]]
- [[_COMMUNITY_UI Design System|UI Design System]]
- [[_COMMUNITY_DateTime Formatting|Date/Time Formatting]]
- [[_COMMUNITY_FastAPI App Entry|FastAPI App Entry]]
- [[_COMMUNITY_Contacts UI|Contacts UI]]
- [[_COMMUNITY_Markdown Editor|Markdown Editor]]
- [[_COMMUNITY_Chat State|Chat State]]
- [[_COMMUNITY_Markdown Rendering|Markdown Rendering]]
- [[_COMMUNITY_UI Design Tokens|UI Design Tokens]]
- [[_COMMUNITY_CLI Entry Point|CLI Entry Point]]
- [[_COMMUNITY_SPA Router|SPA Router]]
- [[_COMMUNITY_Routines UI|Routines UI]]
- [[_COMMUNITY_Knowledge UI|Knowledge UI]]
- [[_COMMUNITY_Vite Build Config|Vite Build Config]]
- [[_COMMUNITY_Channel Dispatch & WhatsApp|Channel Dispatch & WhatsApp]]
- [[_COMMUNITY_Prompt Caching Rationale|Prompt Caching Rationale]]
- [[_COMMUNITY_Release & Issue Workflow|Release & Issue Workflow]]
- [[_COMMUNITY_Channel Dispatcher Docs|Channel Dispatcher Docs]]
- [[_COMMUNITY_Docs Site Shell|Docs Site Shell]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Provider Feature Flags|Provider Feature Flags]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Derived Interaction Field|Derived Interaction Field]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Reminder Schedule Calc|Reminder Schedule Calc]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Vite Config (Docs)|Vite Config (Docs)]]
- [[_COMMUNITY_Svelte Config (UI)|Svelte Config (UI)]]
- [[_COMMUNITY_Bookmarks UI|Bookmarks UI]]
- [[_COMMUNITY_Settings UI|Settings UI]]
- [[_COMMUNITY_Skills UI|Skills UI]]
- [[_COMMUNITY_Setup UI|Setup UI]]
- [[_COMMUNITY_Dashboard UI|Dashboard UI]]
- [[_COMMUNITY_Code Editor UI|Code Editor UI]]
- [[_COMMUNITY_TypeScript Types|TypeScript Types]]
- [[_COMMUNITY_Svelte Config (Docs)|Svelte Config (Docs)]]
- [[_COMMUNITY_Svelte App Types|Svelte App Types]]
- [[_COMMUNITY_Sidebar UI|Sidebar UI]]
- [[_COMMUNITY_Docs Navigation|Docs Navigation]]
- [[_COMMUNITY_Header UI|Header UI]]
- [[_COMMUNITY_Layout UI|Layout UI]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Skill Discovery|Skill Discovery]]
- [[_COMMUNITY_Root SKILL.md Discovery|Root SKILL.md Discovery]]
- [[_COMMUNITY_Skill Subpath Filter|Skill Subpath Filter]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Telegram Channel Adapter|Telegram Channel Adapter]]
- [[_COMMUNITY_Contact Data Model|Contact Data Model]]
- [[_COMMUNITY_Docker Sandbox|Docker Sandbox]]
- [[_COMMUNITY_Docker Deployment|Docker Deployment]]
- [[_COMMUNITY_UI Typography|UI Typography]]

## God Nodes (most connected - your core abstractions)
1. `ToolRegistry` - 209 edges
2. `PluginRegistry` - 169 edges
3. `PluginType` - 142 edges
4. `ToolDefinition` - 133 edges
5. `AgentLoop` - 130 edges
6. `HomeclawConfig` - 112 edges
7. `ChannelDispatcher` - 101 edges
8. `RoutineDefinition` - 100 edges
9. `LLMResponse` - 94 edges
10. `ToolCall` - 89 edges

## Surprising Connections (you probably didn't know these)
- `Memory Layer 1 — Structured Facts (facts.py)` --semantically_similar_to--> `Memory as Markdown Files (workspaces/{person}/memory/{topic}.md)`  [INFERRED] [semantically similar]
  homeclaw-planning-prompt.md → CLAUDE.md
- `test_verify_checksum_empty_skips()` --calls--> `_verify_checksum()`  [INFERRED]
  tests/unit/test_marketplace_installer.py → homeclaw/plugins/marketplace/installer.py
- `test_verify_checksum_mismatch()` --calls--> `_verify_checksum()`  [INFERRED]
  tests/unit/test_marketplace_installer.py → homeclaw/plugins/marketplace/installer.py
- `test_verify_checksum_unsupported_format()` --calls--> `_verify_checksum()`  [INFERRED]
  tests/unit/test_marketplace_installer.py → homeclaw/plugins/marketplace/installer.py
- `Tests for the sandboxed http_call tool.` --uses--> `HttpCallConfig`  [INFERRED]
  tests/unit/test_http_call.py → homeclaw/plugins/skills/http_call.py

## Hyperedges (group relationships)
- **Three-Tier Plugin System** — homeclaw_planning_prompt_plugin_python, homeclaw_planning_prompt_plugin_skill, homeclaw_planning_prompt_plugin_mcp, homeclaw_planning_prompt_plugin_protocol [EXTRACTED 1.00]
- **Two-Layer Memory System** — homeclaw_planning_prompt_memory_layer1, homeclaw_planning_prompt_memory_layer2, homeclaw_planning_prompt_context_builder, homeclaw_planning_prompt_memsearch [EXTRACTED 1.00]
- **LLM Cost Management System** — cost_prompt_routing_config, cost_prompt_call_type_enum, cost_prompt_batch_scheduler, cost_prompt_cost_tracker, readme_prompt_caching [EXTRACTED 0.95]
- **Household Memory Privacy System: per-person workspaces, memsearch scoping, DM enforcement** — concept_memsearch, concept_workspaces_dir, docs_memory_privacy_model, concept_personal_write_tools, docs_architecture_dm_enforcement_rationale [INFERRED 0.85]
- **Three-Tier Plugin System: Python plugins, Skill markdown, MCP sidecars all via Plugin Protocol** — docs_plugins, concept_plugin_protocol, docs_tools [EXTRACTED 0.90]
- **Dev Fixture Household: workspaces-dev with Alice, Bob, contacts for deterministic testing** — about_household, about_alice, about_bob, contact_grandma_eleanor, contact_james_ko, contact_sarah_chen [INFERRED 0.88]

## Communities

### Community 0 - "Auth & API Layer"
Cohesion: 0.01
Nodes (226): AnthropicProvider, login(), LoginBody, Auth API routes — login endpoint that returns JWT session tokens., Exchange credentials for a signed JWT session token.      All logins are member, chat(), chat_history(), _extract_text() (+218 more)

### Community 1 - "Plugin & Tool Registry"
Cohesion: 0.03
Nodes (225): ToolDefinition, get_plugin_registry(), Enum, extract_env_hints(), Scan Python files in *plugin_dir* for environment variable references.      Retu, HttpCallConfig, _download(), _install_mcp() (+217 more)

### Community 2 - "LLM Provider & Caching"
Cohesion: 0.03
Nodes (217): _cacheable_system(), complete(), _is_retryable_anthropic(), _log_cache_usage(), _parse_response(), Anthropic SDK implementation of LLMProvider., Log cache hit/miss at debug level., Return True for transient Anthropic errors worth retrying. (+209 more)

### Community 3 - "App Bootstrap & Config"
Cohesion: 0.02
Nodes (156): _build_parser(), _dry_run(), _ensure_default_files(), HomeclawApp, main(), CLI entry point — ``homeclaw`` starts the household assistant., Async initialization — call after constructing in an event loop., Called by routine tools when ROUTINES.md changes. (+148 more)

### Community 4 - "Web UI State & Auth"
Cohesion: 0.03
Nodes (133): api(), getToken(), save(), Serve the WhatsApp QR code as a PNG image for scanning in the browser.      Retu, whatsapp_qr(), get_contact(), _notes_path(), _save_test_bookmark() (+125 more)

### Community 5 - "Skill Loader & Tools"
Cohesion: 0.03
Nodes (102): build_skill_catalog(), _builtin_skills_dir(), discover_skills(), env(), _find_skill_file(), _is_admin_only(), load_skill(), _load_skill_env() (+94 more)

### Community 6 - "Scheduler & Routines"
Cohesion: 0.03
Nodes (49): get_scheduler(), add_routine(), add_routine_endpoint(), _day_offset(), delete_routine_endpoint(), _extract_schedule_and_actions(), _last_results(), _last_runs() (+41 more)

### Community 7 - "Plugin Marketplace"
Cohesion: 0.03
Nodes (77): download_plugin_repo(), download_skill_repo(), list_repo_plugins(), list_repo_skills(), normalize_gist_url(), parse_github_url(), GitHub skill repository downloader., Convert a gist.github.com URL to a raw download URL.      Returns None if not a (+69 more)

### Community 8 - "Calendar & Events"
Cohesion: 0.04
Nodes (70): calendar_month(), _collect_birthdays(), _collect_interactions(), _collect_notes(), _collect_reminders(), _parse_month(), Calendar API route — unified monthly view., Collect contact interactions within date range. (+62 more)

### Community 9 - "Marketplace Client"
Cohesion: 0.07
Nodes (65): MarketplaceClient, Marketplace index client — fetch, cache, and query available plugins., Load the cached index from disk. Returns None if missing or invalid., Return cached index if available, otherwise an empty index., Write the index to the local cache file., Fetches and caches the remote marketplace plugin index.      Usage::          cl, Whether a marketplace URL has been set., List available plugins, optionally filtered by type.          Uses the cached in (+57 more)

### Community 10 - "Configuration System"
Cohesion: 0.03
Nodes (49): BaseSettings, _JsonFileSource, _normalize_phone(), homeclaw configuration — loads from environment variables, .env, and config.json, Parse allowed user IDs, or None if unrestricted., Parse allowed WhatsApp IDs (phone numbers or LIDs).          Accepts both tradit, Load routing model overrides from config.json if present., Normalize a phone number to digits only, stripping +, spaces, dashes. (+41 more)

### Community 11 - "Memory & Semantic Search"
Cohesion: 0.04
Nodes (40): Built-in web providers — auto-registered on import., Register built-in providers with the global registry., register_builtins(), JinaProvider, Jina AI web search and read provider., Web search and read via Jina AI APIs (s.jina.ai / r.jina.ai)., Protocol, BuiltinProvider (+32 more)

### Community 12 - "Telegram Adapter"
Cohesion: 0.1
Nodes (41): _make_channel(), _make_update(), Unit tests for the Telegram channel adapter., test_agent_error_sends_apology(), test_allowed_user_can_message(), test_disallowed_user_cannot_register(), test_disallowed_user_silently_dropped(), test_dm_does_not_pass_channel() (+33 more)

### Community 13 - "HTTP Tool & Safety"
Cohesion: 0.06
Nodes (50): _check_domain(), _check_global_allow_local(), _check_private_ip(), http_call(), _is_private_ip(), _log_request(), _normalize_domain(), Sandboxed HTTP call tool — domain-allowlisted, blocks private IPs. (+42 more)

### Community 14 - "Tool Schema Generation"
Cohesion: 0.08
Nodes (26): Tests for the tool_decorator module — auto-generating schemas from signatures., TestBasicTypeMapping, TestDescAnnotation, TestKwargsIgnored, TestLiteralAndEnum, TestNoParams, TestOptionalParams, TestRegistration (+18 more)

### Community 15 - "Household Members Data"
Cohesion: 0.05
Nodes (47): Alice: Personal Memory (vegetarian, marketing, Mochi the cat), Alice: Preferences (7:30am reminders, brief/friendly, vegetarian), Alice Note 2026-03-12 (call Mum about Easter), Bob: Personal Memory (runner, cook, kitchen renovation, SWE), Bob: Preferences (8am reminders, detailed communication), DM Person Enforcement (_PERSONAL_WRITE_TOOLS), Memory as Markdown Files (workspaces/{person}/memory/{topic}.md), BatchScheduler (Anthropic Message Batches) (+39 more)

### Community 16 - "Plants Plugin"
Cohesion: 0.09
Nodes (26): _data_path(), get_overdue_plants(), _load_env(), _load_store(), _next_water_str(), Plant, PlantStore, Plugin (+18 more)

### Community 17 - "Bookmarks & Notes"
Cohesion: 0.09
Nodes (36): bookmark_remove(), bookmarks_index(), _notes_for(), Bookmarks API routes — household-shared saved links and places., Read the markdown notes file for a bookmark, if it exists., List or search bookmarks. Use ?q= for search, ?category= or ?tag= to filter., Delete a bookmark by ID., update() (+28 more)

### Community 18 - "Skill Dependency Check"
Cohesion: 0.07
Nodes (23): check_skill_deps(), _install_hint(), _is_docker(), Detect if we're running inside a Docker container., Return a human-readable install hint for a missing binary., Check skill dependencies from metadata.openclaw.requires.      Args:         met, Tests for homeclaw/plugins/skills/deps.py — skill dependency checker., Non-dict openclaw value → treated as satisfied (graceful). (+15 more)

### Community 19 - "Cost Tracking"
Cohesion: 0.12
Nodes (24): cost_summary(), Cost summary API route., _round_breakdown(), CostEntry, CostTracker, estimate_cost(), load_prices(), ModelPricing (+16 more)

### Community 20 - "Tool Use Logging"
Cohesion: 0.13
Nodes (20): Read tool use events from the JSONL log., _tool_use_events(), _log_tool_event(), Read raw tool_use.jsonl entries with full args., _read_tool_log(), _mock_provider(), Tests for tool use event logging and feed reader., Tests for the feed API's tool_use event reader. (+12 more)

### Community 21 - "Core Architecture Concepts"
Cohesion: 0.08
Nodes (31): Household as coherent unit (core design concept), memsearch — Milvus Lite vector DB semantic recall for workspace content, openclaw — mature single-person AI assistant (external project, predecessor/sibling), _PERSONAL_WRITE_TOOLS — list enforcing person-scoped workspace writes in DMs, Plugin Protocol interface (homeclaw/plugins/interface.py), ROUTINES.md — natural language scheduled routines file, workspaces/ directory — per-person and household data storage, Architecture — directory structure, key design decisions (+23 more)

### Community 22 - "Path Safety Utilities"
Cohesion: 0.11
Nodes (11): Path safety utilities — prevent directory traversal in user-supplied inputs., Validate a date string is YYYY-MM-DD format. Returns the validated string., Build a path from parts and verify it stays within the base directory.      Rais, Sanitize a user-supplied string into a safe filesystem slug.      Strips everyth, safe_date(), safe_path_within(), safe_slug(), Tests for path safety utilities. (+3 more)

### Community 23 - "Log Buffer"
Cohesion: 0.1
Nodes (21): get_log_buffer(), get_log_entries_from_file(), install_log_buffer(), _log_entry(), LogBuffer, LogFileHandler, In-memory ring buffer + persistent JSONL file for application logs.  Captures lo, Read JSONL log file with filtering. Returns newest first. (+13 more)

### Community 24 - "Data Export & Import"
Cohesion: 0.14
Nodes (19): _build_zip(), export_data(), import_data(), Data export/import API routes — full household backup and restore., Export all household data as a ZIP archive., Import household data from a previously exported ZIP archive.      Overwrites ex, Walk the workspaces directory and pack exportable files into a ZIP., Extract a ZIP archive into the workspaces directory.      Returns summary statis (+11 more)

### Community 25 - "Terminal REPL"
Cohesion: 0.2
Nodes (10): Terminal REPL channel — runs the agent loop interactively in the terminal., Run an interactive REPL that feeds user input into the agent loop.      Supports, run_repl(), Integration tests for the REPL channel.  Tests mock builtins.input and the Agent, Typing 'exit' should cause run_repl to return without error., A message followed by 'exit' should invoke loop.run() with the message., r"""Lines ending with '\\' should be joined as multiline input., test_repl_exit() (+2 more)

### Community 26 - "Dev Fixture Household"
Cohesion: 0.18
Nodes (12): Alice (household member, vegetarian), Biscuit (cat), Bob (household member), Household: Alice, Bob, Mia, Leo, Leo (child, age 5), Mia (child, age 8), Mochi (cat), Grandma Eleanor (contact, Portland, gardening, cat Whiskers, medication schedule) (+4 more)

### Community 27 - "Dev Fixtures Setup"
Cohesion: 0.43
Nodes (5): _build_manifest(), _json(), _jsonl(), main(), # TODO: Implement once plugin loader is built (homeclaw-jzg)

### Community 28 - "UI Design System"
Cohesion: 0.4
Nodes (5): Design System: The Digital Conservatory, Rationale: Stewardship feel over task management, FastAPI Web UI Backend, Svelte Web UI (ui/), Web UI Entry Point (ui/index.html)

### Community 29 - "Date/Time Formatting"
Cohesion: 0.67
Nodes (2): formatDateTime(), formatRelativeTime()

### Community 30 - "FastAPI App Entry"
Cohesion: 0.67
Nodes (1): FastAPI application — serves REST API and static web UI.

### Community 31 - "Contacts UI"
Cohesion: 0.67
Nodes (0): 

### Community 32 - "Markdown Editor"
Cohesion: 0.67
Nodes (1): active

### Community 33 - "Chat State"
Cohesion: 0.67
Nodes (0): 

### Community 34 - "Markdown Rendering"
Cohesion: 0.67
Nodes (0): 

### Community 35 - "UI Design Tokens"
Cohesion: 0.67
Nodes (3): Color Palette (earth-toned neutrals), Design Rule: No 1px Borders, Surface Hierarchy (surface, surface_container_low, etc.)

### Community 36 - "CLI Entry Point"
Cohesion: 1.0
Nodes (1): Allow running homeclaw as ``python -m homeclaw``.

### Community 37 - "SPA Router"
Cohesion: 1.0
Nodes (0): 

### Community 38 - "Routines UI"
Cohesion: 1.0
Nodes (0): 

### Community 39 - "Knowledge UI"
Cohesion: 1.0
Nodes (0): 

### Community 40 - "Vite Build Config"
Cohesion: 1.0
Nodes (0): 

### Community 41 - "Channel Dispatch & WhatsApp"
Cohesion: 1.0
Nodes (2): Channel Dispatcher, WhatsApp Channel Adapter (neonize)

### Community 42 - "Prompt Caching Rationale"
Cohesion: 1.0
Nodes (2): Rationale: 90% discount via Anthropic prompt caching, Anthropic Prompt Caching (cache_control)

### Community 43 - "Release & Issue Workflow"
Cohesion: 1.0
Nodes (2): beads_rust (br) Issue Tracking, release-please Conventional Commits Workflow

### Community 44 - "Channel Dispatcher Docs"
Cohesion: 1.0
Nodes (2): Channel dispatcher — routes outbound messages to person's preferred channel, Channels guide — Web UI, Telegram, WhatsApp, REPL, channel dispatcher

### Community 45 - "Docs Site Shell"
Cohesion: 1.0
Nodes (2): Docs site HTML shell (SvelteKit app.html), Favicon: house emoji icon (🏠) — represents homeclaw brand

### Community 46 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 47 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 48 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 49 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 50 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 51 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 52 - "Provider Feature Flags"
Cohesion: 1.0
Nodes (1): Adjust features based on provider mode.

### Community 53 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 54 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 55 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 56 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 57 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 58 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 59 - "Derived Interaction Field"
Cohesion: 1.0
Nodes (1): Derived from the most recent interaction — no longer stored separately.

### Community 60 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 61 - "Reminder Schedule Calc"
Cohesion: 1.0
Nodes (1): Calculate when this reminder is next due.

### Community 62 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 63 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 64 - "Vite Config (Docs)"
Cohesion: 1.0
Nodes (0): 

### Community 65 - "Svelte Config (UI)"
Cohesion: 1.0
Nodes (0): 

### Community 66 - "Bookmarks UI"
Cohesion: 1.0
Nodes (0): 

### Community 67 - "Settings UI"
Cohesion: 1.0
Nodes (0): 

### Community 68 - "Skills UI"
Cohesion: 1.0
Nodes (0): 

### Community 69 - "Setup UI"
Cohesion: 1.0
Nodes (0): 

### Community 70 - "Dashboard UI"
Cohesion: 1.0
Nodes (0): 

### Community 71 - "Code Editor UI"
Cohesion: 1.0
Nodes (0): 

### Community 72 - "TypeScript Types"
Cohesion: 1.0
Nodes (0): 

### Community 73 - "Svelte Config (Docs)"
Cohesion: 1.0
Nodes (0): 

### Community 74 - "Svelte App Types"
Cohesion: 1.0
Nodes (0): 

### Community 75 - "Sidebar UI"
Cohesion: 1.0
Nodes (0): 

### Community 76 - "Docs Navigation"
Cohesion: 1.0
Nodes (0): 

### Community 77 - "Header UI"
Cohesion: 1.0
Nodes (0): 

### Community 78 - "Layout UI"
Cohesion: 1.0
Nodes (0): 

### Community 79 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 80 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 81 - "Skill Discovery"
Cohesion: 1.0
Nodes (1): Finds SKILL.md files in subdirectories.

### Community 82 - "Root SKILL.md Discovery"
Cohesion: 1.0
Nodes (1): A SKILL.md at the repo root is also found (path='').

### Community 83 - "Skill Subpath Filter"
Cohesion: 1.0
Nodes (1): Only returns skills under the specified subpath.

### Community 84 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 85 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 86 - "Module Init"
Cohesion: 1.0
Nodes (0): 

### Community 87 - "Telegram Channel Adapter"
Cohesion: 1.0
Nodes (1): Telegram Channel Adapter

### Community 88 - "Contact Data Model"
Cohesion: 1.0
Nodes (1): Contact Pydantic Model

### Community 89 - "Docker Sandbox"
Cohesion: 1.0
Nodes (1): Docker Sandbox (macOS MicroVM isolation)

### Community 90 - "Docker Deployment"
Cohesion: 1.0
Nodes (1): Docker Deployment

### Community 91 - "UI Typography"
Cohesion: 1.0
Nodes (1): Typography: Newsreader (serif) + Plus Jakarta Sans

## Knowledge Gaps
- **268 isolated node(s):** `Path safety utilities — prevent directory traversal in user-supplied inputs.`, `Sanitize a user-supplied string into a safe filesystem slug.      Strips everyth`, `Validate a date string is YYYY-MM-DD format. Returns the validated string.`, `Build a path from parts and verify it stays within the base directory.      Rais`, `Per-key async lock pool — prevents concurrent read-modify-write races.` (+263 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `CLI Entry Point`** (2 nodes): `__main__.py`, `Allow running homeclaw as ``python -m homeclaw``.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `SPA Router`** (2 nodes): `App.svelte`, `main.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Routines UI`** (2 nodes): `var()`, `Routines.svelte`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Knowledge UI`** (2 nodes): `fetchNoteDetail()`, `Knowledge.svelte`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Vite Build Config`** (2 nodes): `vite.config.js`, `getVersion()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Channel Dispatch & WhatsApp`** (2 nodes): `Channel Dispatcher`, `WhatsApp Channel Adapter (neonize)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Prompt Caching Rationale`** (2 nodes): `Rationale: 90% discount via Anthropic prompt caching`, `Anthropic Prompt Caching (cache_control)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Release & Issue Workflow`** (2 nodes): `beads_rust (br) Issue Tracking`, `release-please Conventional Commits Workflow`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Channel Dispatcher Docs`** (2 nodes): `Channel dispatcher — routes outbound messages to person's preferred channel`, `Channels guide — Web UI, Telegram, WhatsApp, REPL, channel dispatcher`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Docs Site Shell`** (2 nodes): `Docs site HTML shell (SvelteKit app.html)`, `Favicon: house emoji icon (🏠) — represents homeclaw brand`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Provider Feature Flags`** (1 nodes): `Adjust features based on provider mode.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Derived Interaction Field`** (1 nodes): `Derived from the most recent interaction — no longer stored separately.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Reminder Schedule Calc`** (1 nodes): `Calculate when this reminder is next due.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Vite Config (Docs)`** (1 nodes): `vite.config.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Svelte Config (UI)`** (1 nodes): `svelte.config.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Bookmarks UI`** (1 nodes): `Bookmarks.svelte`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Settings UI`** (1 nodes): `Settings.svelte`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Skills UI`** (1 nodes): `Skills.svelte`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Setup UI`** (1 nodes): `Setup.svelte`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Dashboard UI`** (1 nodes): `Dashboard.svelte`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Code Editor UI`** (1 nodes): `CodeEditor.svelte`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `TypeScript Types`** (1 nodes): `types.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Svelte Config (Docs)`** (1 nodes): `svelte.config.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Svelte App Types`** (1 nodes): `app.d.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Sidebar UI`** (1 nodes): `Sidebar.svelte`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Docs Navigation`** (1 nodes): `nav.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Header UI`** (1 nodes): `Header.svelte`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Layout UI`** (1 nodes): `+layout.svelte`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Skill Discovery`** (1 nodes): `Finds SKILL.md files in subdirectories.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Root SKILL.md Discovery`** (1 nodes): `A SKILL.md at the repo root is also found (path='').`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Skill Subpath Filter`** (1 nodes): `Only returns skills under the specified subpath.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Telegram Channel Adapter`** (1 nodes): `Telegram Channel Adapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Contact Data Model`** (1 nodes): `Contact Pydantic Model`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Docker Sandbox`** (1 nodes): `Docker Sandbox (macOS MicroVM isolation)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Docker Deployment`** (1 nodes): `Docker Deployment`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `UI Typography`** (1 nodes): `Typography: Newsreader (serif) + Plus Jakarta Sans`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ToolRegistry` connect `Plugin & Tool Registry` to `Auth & API Layer`, `LLM Provider & Caching`, `App Bootstrap & Config`, `Web UI State & Auth`, `Skill Loader & Tools`, `Calendar & Events`, `Marketplace Client`, `Memory & Semantic Search`, `Tool Schema Generation`?**
  _High betweenness centrality (0.154) - this node is a cross-community bridge._
- **Why does `AgentLoop` connect `App Bootstrap & Config` to `Auth & API Layer`, `Plugin & Tool Registry`, `LLM Provider & Caching`, `Terminal REPL`?**
  _High betweenness centrality (0.098) - this node is a cross-community bridge._
- **Why does `PluginRegistry` connect `Plugin & Tool Registry` to `LLM Provider & Caching`, `App Bootstrap & Config`, `Skill Loader & Tools`, `Marketplace Client`, `Memory & Semantic Search`?**
  _High betweenness centrality (0.076) - this node is a cross-community bridge._
- **Are the 201 inferred relationships involving `ToolRegistry` (e.g. with `HomeclawApp` and `CLI entry point — ``homeclaw`` starts the household assistant.`) actually correct?**
  _`ToolRegistry` has 201 INFERRED edges - model-reasoned connections that need verification._
- **Are the 156 inferred relationships involving `PluginRegistry` (e.g. with `HomeclawApp` and `CLI entry point — ``homeclaw`` starts the household assistant.`) actually correct?**
  _`PluginRegistry` has 156 INFERRED edges - model-reasoned connections that need verification._
- **Are the 140 inferred relationships involving `PluginType` (e.g. with `PluginLoadError` and `Skill plugin loader — parses SKILL.md files with YAML frontmatter.`) actually correct?**
  _`PluginType` has 140 INFERRED edges - model-reasoned connections that need verification._
- **Are the 131 inferred relationships involving `ToolDefinition` (e.g. with `Plant` and `PlantStore`) actually correct?**
  _`ToolDefinition` has 131 INFERRED edges - model-reasoned connections that need verification._
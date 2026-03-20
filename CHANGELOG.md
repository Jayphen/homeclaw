# Changelog

## [0.5.1](https://github.com/Jayphen/homeclaw/compare/v0.5.0...v0.5.1) (2026-03-20)


### Bug Fixes

* admin toggle uses optimistic update to prevent scroll jump ([21956d5](https://github.com/Jayphen/homeclaw/commit/21956d5e4eef7cb817f16f77ef09c0f843ccd63f))
* bootstrap admin — first member account auto-promotes to admin ([9e8c53d](https://github.com/Jayphen/homeclaw/commit/9e8c53dba1344dc7980520dababe5b424b3e1b57))
* normalize WhatsApp phone numbers for flexible matching ([259c97b](https://github.com/Jayphen/homeclaw/commit/259c97be72275b09470af513da8361f388d6b263))

## [0.5.0](https://github.com/Jayphen/homeclaw/compare/v0.4.5...v0.5.0) (2026-03-20)


### ⚠ BREAKING CHANGES

* replace separate admin with member-level admin role

### Features

* replace separate admin with member-level admin role ([d188036](https://github.com/Jayphen/homeclaw/commit/d188036d78450a05b1ecd90d5d6325e57553e96c))


### Bug Fixes

* properly render block-level markdown in previews ([b73656e](https://github.com/Jayphen/homeclaw/commit/b73656e3497b3ec1a20b1567004e71741bb5b771))
* setup POST auth now accepts JWT tokens (admin required) ([da8885e](https://github.com/Jayphen/homeclaw/commit/da8885e5a87ed6760e221a339f2330eafcdd20d9))
* use full markdown rendering for note previews ([feba6b7](https://github.com/Jayphen/homeclaw/commit/feba6b77c7a6e931ce61ccc7755166228e2a7715))

## [0.4.5](https://github.com/Jayphen/homeclaw/compare/v0.4.4...v0.4.5) (2026-03-20)


### Bug Fixes

* calendar route uses real reminder store, reads notes efficiently ([247f8f3](https://github.com/Jayphen/homeclaw/commit/247f8f3cd47a5dd095578fe0046dbf95cc66c90e))
* import clearToken so sign-out button works ([09a348f](https://github.com/Jayphen/homeclaw/commit/09a348f9062931a86970e1fb98be54b9119e83cc))
* render markdown in calendar summaries and note previews ([73650d5](https://github.com/Jayphen/homeclaw/commit/73650d5e8aa0b44dbeed24483e45adc87796a13a))

## [0.4.4](https://github.com/Jayphen/homeclaw/compare/v0.4.3...v0.4.4) (2026-03-20)


### Features

* improve skill data management and fix agent history leaking ([f195ab1](https://github.com/Jayphen/homeclaw/commit/f195ab15b50fa4e6c13355f7ea3a5681e4847014))

## [0.4.3](https://github.com/Jayphen/homeclaw/compare/v0.4.2...v0.4.3) (2026-03-20)


### Features

* add member account management UI and sign-out button ([34c0bf9](https://github.com/Jayphen/homeclaw/commit/34c0bf9ca9bb80892d51480844c6cd899a388bde))


### Bug Fixes

* install libmagic in Docker, show WhatsApp QR in settings UI ([0c21ddb](https://github.com/Jayphen/homeclaw/commit/0c21ddb9553d7664ad9cf526e483ee717f977206))

## [0.4.2](https://github.com/Jayphen/homeclaw/compare/v0.4.1...v0.4.2) (2026-03-20)


### Features

* add logger filter pills and horizontal scroll to log viewer ([349d135](https://github.com/Jayphen/homeclaw/commit/349d135c5f217010ea084c8e9c70ff22f0561ba4))
* return routine results to calling agent, disable ARM CI build ([d74a574](https://github.com/Jayphen/homeclaw/commit/d74a5746017f0e3baadf910f3d82dcd05142e458))

## [0.4.1](https://github.com/Jayphen/homeclaw/compare/v0.4.0...v0.4.1) (2026-03-20)


### Features

* add timezone config for scheduler and log timestamps ([c990c52](https://github.com/Jayphen/homeclaw/commit/c990c528f45e9d2d585eeac59b610d8d849c68b7))
* add timezone setting to web UI ([1d659fb](https://github.com/Jayphen/homeclaw/commit/1d659fb800fca744c458b0a6121308e80a8c0db4))


### Bug Fixes

* add misfire_grace_time and routine_run tool to fix silent schedule skips ([716f8d2](https://github.com/Jayphen/homeclaw/commit/716f8d29a2d5e39464d174d15ad65c6926f91093))
* add misfire_grace_time and routine_run tool to fix silent schedule skips ([4a83762](https://github.com/Jayphen/homeclaw/commit/4a8376267ddd4229e8cb64b50d89afefe7c777e7))
* detect and fire missed routines after server restart ([cbd9cfb](https://github.com/Jayphen/homeclaw/commit/cbd9cfb3e0fffcdd40f1be9643a8f025da055bbb))

## [0.4.0](https://github.com/Jayphen/homeclaw/compare/v0.3.14...v0.4.0) (2026-03-19)


### ⚠ BREAKING CHANGES

* harden web API auth — bcrypt, JWT sessions, authorization fixes

### Features

* add install/uninstall API routes for marketplace plugins ([5941e01](https://github.com/Jayphen/homeclaw/commit/5941e01a2842879e0c4620e5d7d956f64ee02dbf))
* add marketplace plugin installer with install/uninstall API ([93e9683](https://github.com/Jayphen/homeclaw/commit/93e96830320a6da1c807bb2dcaff2e8bc800708a))
* add per-member authentication and access control to web API ([15c7d62](https://github.com/Jayphen/homeclaw/commit/15c7d626be9d020fe4ce65331e9953ffe3c08a11))
* harden web API auth — bcrypt, JWT sessions, authorization fixes ([35befe5](https://github.com/Jayphen/homeclaw/commit/35befe57295593fee3aa48da1a9ec33242d8bf44))


### Bug Fixes

* strengthen system prompt to save info the user expects remembered ([7365a42](https://github.com/Jayphen/homeclaw/commit/7365a42a1ab3426bb1b6f0d8065f6e725a177b29))

## [0.3.14](https://github.com/Jayphen/homeclaw/compare/v0.3.13...v0.3.14) (2026-03-19)


### Features

* add bookmark_note_delete tool and fix note quality ([193cf36](https://github.com/Jayphen/homeclaw/commit/193cf36ed9bff3d3849e81be275d80dd6164c18f))
* add embedding_provider config field ([1f5c91a](https://github.com/Jayphen/homeclaw/commit/1f5c91aa467d482162416f2ad73110bb613b33ab))


### Bug Fixes

* auto-reset Milvus collection on embedding dimension mismatch ([63cea43](https://github.com/Jayphen/homeclaw/commit/63cea43379e90b551efbd4e5545df708484a73a1))

## [0.3.13](https://github.com/Jayphen/homeclaw/compare/v0.3.12...v0.3.13) (2026-03-19)


### Bug Fixes

* use local embeddings when API key is not a real OpenAI key ([b9d207f](https://github.com/Jayphen/homeclaw/commit/b9d207f9b0995d686a6cf2e71cb13db58d98d2ed))

## [0.3.12](https://github.com/Jayphen/homeclaw/compare/v0.3.11...v0.3.12) (2026-03-19)


### Bug Fixes

* reinstall package after copying full source in Dockerfile ([f585c38](https://github.com/Jayphen/homeclaw/commit/f585c3829c61574048b9562a16c5c78b112a2401))

## [0.3.11](https://github.com/Jayphen/homeclaw/compare/v0.3.10...v0.3.11) (2026-03-19)


### Bug Fixes

* use CPU-only torch in Docker and improve layer caching ([016daea](https://github.com/Jayphen/homeclaw/commit/016daeab51e0a6dacebaa4aa1264e35792361c96))

## [0.3.10](https://github.com/Jayphen/homeclaw/compare/v0.3.9...v0.3.10) (2026-03-19)


### Features

* add installed plugins and marketplace sections to Plugins view ([a92a875](https://github.com/Jayphen/homeclaw/commit/a92a8757d7b44724da2001ab140fa0f3059699ca))
* add plugins API routes (GET /api/plugins, GET /api/plugins/{name}, marketplace browse) ([ccef3ff](https://github.com/Jayphen/homeclaw/commit/ccef3ff90e7b3ece86df2ffd3039affb0ce64d67))
* show app version in Settings page and fix FastAPI version ([0796114](https://github.com/Jayphen/homeclaw/commit/07961141bf6164dccff28b94a4645c234931439a))
* user-installed plugins are opt-in, disabled by default ([2d0bd28](https://github.com/Jayphen/homeclaw/commit/2d0bd287be5f7de42e6a15a3a8b511fdc0e051e3))


### Bug Fixes

* pin pymilvus &lt;2.6, fix memsearch[local] extra, and add startup logging ([c2e220a](https://github.com/Jayphen/homeclaw/commit/c2e220a5fffd7baeffa719316b30fad73cf16cd3))

## [0.3.9](https://github.com/Jayphen/homeclaw/compare/v0.3.8...v0.3.9) (2026-03-19)


### Bug Fixes

* default to local embeddings and fix setup/status 401 ([64325a2](https://github.com/Jayphen/homeclaw/commit/64325a273b9ea0b6e26386dda868780bf47ea211))


### Documentation

* add Docker deployment guide to README ([b5f3710](https://github.com/Jayphen/homeclaw/commit/b5f3710989192a4cc4ea6c77161a74e52cc37ec8))
* clarify Docker setup is done via web UI, not env vars ([d72e496](https://github.com/Jayphen/homeclaw/commit/d72e49671a519fa4686d8025c259b8ef7a1f1c2d))

## [0.3.8](https://github.com/Jayphen/homeclaw/compare/v0.3.7...v0.3.8) (2026-03-19)


### Bug Fixes

* password timing attack, unauthenticated endpoints, unbounded writes ([9c33dab](https://github.com/Jayphen/homeclaw/commit/9c33dabfa3dfc4f7d5e45a6f736bcae76500a03b))

## [0.3.7](https://github.com/Jayphen/homeclaw/compare/v0.3.6...v0.3.7) (2026-03-19)


### Features

* add decision logging tool and context injection ([6df69af](https://github.com/Jayphen/homeclaw/commit/6df69af27003bb272f8c086c616cfce1c566555f))
* add proactive behavior guidance to system prompt ([415415c](https://github.com/Jayphen/homeclaw/commit/415415c6ba728c2473f070b6f351590b035d84fd))
* consolidate tool selection guidance with examples in system prompt ([da1c72e](https://github.com/Jayphen/homeclaw/commit/da1c72ea132e305fe4c8239acf2382bef0351594))
* enrich context builder with notes, routines, and memory topics ([2a6c5af](https://github.com/Jayphen/homeclaw/commit/2a6c5afd5ece2a5b14eac1a4c560a1458ebc4b84))


### Bug Fixes

* path traversal and CORS security vulnerabilities ([7046bf4](https://github.com/Jayphen/homeclaw/commit/7046bf4d00bf3d5c4fad4adc27cc312688c70abb))
* sanitize markdown rendering with DOMPurify to prevent XSS ([4cd3e60](https://github.com/Jayphen/homeclaw/commit/4cd3e60ddfdca99a7fe39527064cdd44092453e7))

## [0.3.6](https://github.com/Jayphen/homeclaw/compare/v0.3.5...v0.3.6) (2026-03-19)


### Features

* add agent personality and household profile injection ([1684190](https://github.com/Jayphen/homeclaw/commit/16841904d4f2eaea01ad71aa7e2810124565feb9))
* add application log viewer to Settings page ([04af7a3](https://github.com/Jayphen/homeclaw/commit/04af7a3699c4ccbe575931faec0687cf61f6800c))


### Bug Fixes

* inject current speaker's name into system prompt context ([574e4f1](https://github.com/Jayphen/homeclaw/commit/574e4f17ffa81d8d81ffe364add01004e579a35b))

## [0.3.5](https://github.com/Jayphen/homeclaw/compare/v0.3.4...v0.3.5) (2026-03-19)


### Features

* add channel dispatcher for outbound message delivery ([e8c37bc](https://github.com/Jayphen/homeclaw/commit/e8c37bcb5d5bd8178bff1b481c6504039538ecf2))
* add WhatsApp channel adapter via neonize ([54c9c9d](https://github.com/Jayphen/homeclaw/commit/54c9c9dbf705c7366f4313adbb72d3cd08f17612))
* add WhatsApp photo handling and include neonize in Docker image ([91dd301](https://github.com/Jayphen/homeclaw/commit/91dd301e42f89689d2664178154a649e68898671))
* add WhatsApp to setup API and web UI ([f5c75e9](https://github.com/Jayphen/homeclaw/commit/f5c75e9aadd15cf89ca36c05ce6b88f8df2e7bfd))
* improve routine web searches and add routine_update tool ([a93a49a](https://github.com/Jayphen/homeclaw/commit/a93a49a697f1c3a88d5c9f30dc4081e5a87ef273))
* use telegramify-markdown for proper Telegram formatting ([f03b05e](https://github.com/Jayphen/homeclaw/commit/f03b05e18de5009423d4b35b166dc6abb17b0daf))
* WhatsApp pairing code auth, QR endpoint, reconnection logging, and tests ([646f2f2](https://github.com/Jayphen/homeclaw/commit/646f2f203324d5435bba3014df1679043d84ea0e))


### Documentation

* add WhatsApp channel and dispatcher docs to CLAUDE.md ([1c43c11](https://github.com/Jayphen/homeclaw/commit/1c43c1133e08598c1aa49176b614a16f267faecf))

## [0.3.4](https://github.com/Jayphen/homeclaw/compare/v0.3.3...v0.3.4) (2026-03-18)


### Features

* add bookmark_note_edit tool for editing existing notes ([5ad398f](https://github.com/Jayphen/homeclaw/commit/5ad398f7026a47c44cd26bb15cae6a7e1333880e))
* add markdown editor component with toolbar and live preview ([88187d7](https://github.com/Jayphen/homeclaw/commit/88187d7d8f73db4668388e421e768824078e8de2))
* add marketplace index client with caching and typed models ([3a35699](https://github.com/Jayphen/homeclaw/commit/3a35699b4f28ed33f412ddb29e58db0527a4306b))
* add note editing via web UI ([5b253db](https://github.com/Jayphen/homeclaw/commit/5b253dbbd0064b1fcbd842a17d1c667c93da385c))


### Bug Fixes

* handle None choices from OpenRouter/OpenAI response ([caa2a8c](https://github.com/Jayphen/homeclaw/commit/caa2a8cd4ddea9a2800e20084f6f86d953c1c80e))
* log full LLM response when choices is empty ([b1e4246](https://github.com/Jayphen/homeclaw/commit/b1e4246337af9807864f827ee6cad7c32957cae7))


### Documentation

* add web UI section to CLAUDE.md ([4ff9988](https://github.com/Jayphen/homeclaw/commit/4ff99887d5083a73dc7a558709cc66eda653b767))

## [0.3.3](https://github.com/Jayphen/homeclaw/compare/v0.3.2...v0.3.3) (2026-03-18)


### Features

* add data tools to skills and fix tool name validation ([dcc6a65](https://github.com/Jayphen/homeclaw/commit/dcc6a65d264620a8635e4fa26aa68d38a546628c))
* expand schedule parsing with more patterns and cron expression support ([d6361c4](https://github.com/Jayphen/homeclaw/commit/d6361c458198f6d7fea6645e85a63e366ad753e1))

## [0.3.2](https://github.com/Jayphen/homeclaw/compare/v0.3.1...v0.3.2) (2026-03-18)


### Features

* add skill archive management API and web UI ([1dfd9d0](https://github.com/Jayphen/homeclaw/commit/1dfd9d0254166f69ec0f9a693e4f5ada6b9d9ade))


### Bug Fixes

* add bookmark_update tool so agent can edit URL, title, category, and tags ([88e13bc](https://github.com/Jayphen/homeclaw/commit/88e13bc760ca440ac384682df8b86f401f88ecce))

## [0.3.1](https://github.com/Jayphen/homeclaw/compare/v0.3.0...v0.3.1) (2026-03-18)


### Features

* add skill self-management tools (skill_list, skill_create, skill_remove, skill_migrate) ([afc30eb](https://github.com/Jayphen/homeclaw/commit/afc30eb4b3a465f3f0b42c53edc4e5b9346e8aee))

## [0.3.0](https://github.com/Jayphen/homeclaw/compare/v0.2.0...v0.3.0) (2026-03-18)


### ⚠ BREAKING CHANGES

* neighborhood and city fields removed from Bookmark.

### Bug Fixes

* instruct agent to check for duplicate bookmarks before saving ([f5dc3a4](https://github.com/Jayphen/homeclaw/commit/f5dc3a4b3a6792cae51196738bbdd18d243b1eab))


### Code Refactoring

* remove neighborhood/city from bookmarks, use notes instead ([2b3a00f](https://github.com/Jayphen/homeclaw/commit/2b3a00f0625b919ffbf28c1ff6c6f247f5618e62))

## [0.2.0](https://github.com/Jayphen/homeclaw/compare/v0.1.9...v0.2.0) (2026-03-18)


### ⚠ BREAKING CHANGES

* facts field removed from Contact model.
* memory_update tool replaced by memory_save, household_share now takes topic+content instead of fact.

### Features

* add bookmark_note tool, remove notes field from bookmarks ([6349c4e](https://github.com/Jayphen/homeclaw/commit/6349c4ec43624140a369e38f0b9fad04424a20ca))
* add bookmarks API route and UI view ([b58dada](https://github.com/Jayphen/homeclaw/commit/b58dada025ef07b810d93cf8f6f9436aefb5b602))
* replace contact facts with markdown notes ([6a64559](https://github.com/Jayphen/homeclaw/commit/6a64559175f2e1c3ce29009ba605d1fbc4fde66d))
* replace JSON memory with markdown topics and semantic recall ([bcaf700](https://github.com/Jayphen/homeclaw/commit/bcaf7007c66f7646055a7355046aecd5263282b3))
* show bookmark notes in the web UI ([7fd310b](https://github.com/Jayphen/homeclaw/commit/7fd310b852ca28e09ea7f9a060d3deaad3f8cc5e))
* show typing indicator in Telegram while bot is processing ([c7d4630](https://github.com/Jayphen/homeclaw/commit/c7d4630585ad25285f097807ff7ec8c169022796))


### Bug Fixes

* allow list values in memory preferences to prevent 500 ([6e7159b](https://github.com/Jayphen/homeclaw/commit/6e7159b07e06a39911f95bc279db978ff62a8eee))
* instruct agent to proactively store memory about household members ([e0055a4](https://github.com/Jayphen/homeclaw/commit/e0055a46c0d665f3f62d48fe17cf3386fbad40e5))
* resolve 3 new P1 state drift issues from re-audit ([7cd796f](https://github.com/Jayphen/homeclaw/commit/7cd796f931d2c1d4cb5d0836fd7f74a3b54557cd))
* use memsearch file watcher for live reindexing ([ca71bd7](https://github.com/Jayphen/homeclaw/commit/ca71bd7be0881f6bb67b9bc9b976deedfa3ba1b1))

## [0.1.9](https://github.com/Jayphen/homeclaw/compare/v0.1.8...v0.1.9) (2026-03-18)


### Features

* add data export/import buttons to Settings page ([9dc7fd1](https://github.com/Jayphen/homeclaw/commit/9dc7fd1354b1c7008a43b8aadcd7cbfc702044db))


### Bug Fixes

* handle missing workspaces dir and milvus-lite failures in memory page ([ab2bc41](https://github.com/Jayphen/homeclaw/commit/ab2bc4133ea68ea0ace4ecd8c351fbd0507dabce))
* normalize person names to lowercase to prevent duplicate workspaces ([fae9763](https://github.com/Jayphen/homeclaw/commit/fae9763eec2cd462dcb9b703fe0b28a8babaaf9b))
* resolve P1 and P2 state drift issues from audit ([f625ea8](https://github.com/Jayphen/homeclaw/commit/f625ea8040ed1a4f02408f3fd9eb1ab7a04a2719))

## [0.1.8](https://github.com/Jayphen/homeclaw/compare/v0.1.7...v0.1.8) (2026-03-18)


### Features

* explicit provider selection in config, setup, and settings UI ([a6af2c0](https://github.com/Jayphen/homeclaw/commit/a6af2c04ff1142ada3f910722ec5f4af2040e6a6))

## [0.1.7](https://github.com/Jayphen/homeclaw/compare/v0.1.6...v0.1.7) (2026-03-18)


### Bug Fixes

* move Docker build into release-please workflow ([ba15c9f](https://github.com/Jayphen/homeclaw/commit/ba15c9f4c5e66d65a93479025770f0ded11a3958))

## [0.1.6](https://github.com/Jayphen/homeclaw/compare/v0.1.5...v0.1.6) (2026-03-18)


### Bug Fixes

* P1 state drift fixes — routing defaults, shared config, scheduler reload ([f268991](https://github.com/Jayphen/homeclaw/commit/f268991c99d71352ded09fdc7b0fc539153d1460))
* P2 state drift fixes — model routing, constants, validators, exhaustion ([9b33de9](https://github.com/Jayphen/homeclaw/commit/9b33de9bc32a628cfe2bb63e5333e442907fea39))

## [0.1.5](https://github.com/Jayphen/homeclaw/compare/v0.1.4...v0.1.5) (2026-03-18)


### Bug Fixes

* clear other provider keys when switching providers in setup ([e42b8fb](https://github.com/Jayphen/homeclaw/commit/e42b8fb8533478c7f9342051746600101d311c91))
* trigger Docker build on release instead of tag push ([ce39a78](https://github.com/Jayphen/homeclaw/commit/ce39a78cd3d424622692cefa6d3cd555e88a887c))

## [0.1.4](https://github.com/Jayphen/homeclaw/compare/v0.1.3...v0.1.4) (2026-03-18)


### Bug Fixes

* deferred Telegram start, provider guard, setup UI defaults ([7db7fd5](https://github.com/Jayphen/homeclaw/commit/7db7fd5283e2a5d945121fc483331c08e6a25444))

## [0.1.3](https://github.com/Jayphen/homeclaw/compare/v0.1.2...v0.1.3) (2026-03-18)


### Bug Fixes

* add bookmark_save to DM person enforcement, fix reminder_set → reminder_add ([9748a32](https://github.com/Jayphen/homeclaw/commit/9748a325835db9f2ee8c5014dbf7424ad45b00d5))
* add per-key locks to prevent concurrent file write races ([f7219e5](https://github.com/Jayphen/homeclaw/commit/f7219e5ab69473dc916500cee8e9f96a2bdd9909))
* add registration lock, handle batch terminal states, unify routing config ([e223b37](https://github.com/Jayphen/homeclaw/commit/e223b3724793dbcdbfb7c5063704e615a42694b8))
* auth error state, ChatType constants, RoutingConfig validator ([5d36e01](https://github.com/Jayphen/homeclaw/commit/5d36e01bd6baa4d39130ec2ac6ef4296be9fc373))
* batch scheduler lock, widen registration lock, unify skip sets ([6cc8d9a](https://github.com/Jayphen/homeclaw/commit/6cc8d9a80ede42e90c7e222258e30d4839d6cfa6))
* enforce person attribution for personal tools in DMs ([31b18d9](https://github.com/Jayphen/homeclaw/commit/31b18d9e1c5ff4fef10465bb427d58e544c21af5))
* extract shared list_member_workspaces, fix dashboard reminders, warn on loop exhaustion ([4e66842](https://github.com/Jayphen/homeclaw/commit/4e66842cabf03a251bc02a6be46c6021686f1c60))
* rename Reminder to ContactReminder, derive last_contact from interactions ([7b7426d](https://github.com/Jayphen/homeclaw/commit/7b7426dff91d73c399a7599ac2aea1dcc1ea6b93))


### Documentation

* add DM person enforcement rule to CLAUDE.md ([4a457bb](https://github.com/Jayphen/homeclaw/commit/4a457bb2a064006134c1a7892885876a2bcc250d))

## [0.1.2](https://github.com/Jayphen/homeclaw/compare/v0.1.1...v0.1.2) (2026-03-17)


### Features

* add contacts page with search, list, and detail view ([bc86595](https://github.com/Jayphen/homeclaw/commit/bc86595d5e12f258c2e94d736881a38c72a413eb))
* add data export/import API for household backup and migration ([aa671b9](https://github.com/Jayphen/homeclaw/commit/aa671b95d57a8091339a0d40014dd6a7340fd684))
* add max_tokens routing and surface agent errors in Telegram ([68a8a78](https://github.com/Jayphen/homeclaw/commit/68a8a7840da63b5228d77b1eede14bd63ecbd150))

## [0.1.1](https://github.com/Jayphen/homeclaw/compare/v0.1.0...v0.1.1) (2026-03-17)


### Features

* add data export/import API for household backup and migration ([aa671b9](https://github.com/Jayphen/homeclaw/commit/aa671b95d57a8091339a0d40014dd6a7340fd684))
* add max_tokens routing and surface agent errors in Telegram ([68a8a78](https://github.com/Jayphen/homeclaw/commit/68a8a7840da63b5228d77b1eede14bd63ecbd150))

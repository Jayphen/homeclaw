# Changelog

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

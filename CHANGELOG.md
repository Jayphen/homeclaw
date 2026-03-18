# Changelog

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

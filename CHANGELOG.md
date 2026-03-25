# Changelog

## [0.22.1](https://github.com/Jayphen/homeclaw/compare/v0.22.0...v0.22.1) (2026-03-25)


### Bug Fixes

* **agent:** make notes journal-style with multi-line support ([#106](https://github.com/Jayphen/homeclaw/issues/106)) ([95354de](https://github.com/Jayphen/homeclaw/commit/95354de171e7128b7f10005115e466f49355fd91))
* **api:** hoist lazy imports in setup status endpoint ([#108](https://github.com/Jayphen/homeclaw/issues/108)) ([80a5b14](https://github.com/Jayphen/homeclaw/commit/80a5b144705611f987a2585096583e1dcfd0966f))

## [0.22.0](https://github.com/Jayphen/homeclaw/compare/v0.21.1...v0.22.0) (2026-03-25)


### Features

* index homeclaw docs in memsearch for self-referencing ([#100](https://github.com/Jayphen/homeclaw/issues/100)) ([da4d2a4](https://github.com/Jayphen/homeclaw/commit/da4d2a4139645e8845754779d0777311ec1970c3))


### Bug Fixes

* **ui:** restore API-based .env detection in skill file viewer ([#104](https://github.com/Jayphen/homeclaw/issues/104)) ([946043a](https://github.com/Jayphen/homeclaw/commit/946043a7964d31a2e2c358d7f951648ac2175f22))

## [0.21.1](https://github.com/Jayphen/homeclaw/compare/v0.21.0...v0.21.1) (2026-03-24)


### Bug Fixes

* handle http_call headers passed as JSON string instead of dict ([#98](https://github.com/Jayphen/homeclaw/issues/98)) ([53e3f6e](https://github.com/Jayphen/homeclaw/commit/53e3f6e8d6ab98fcc71ee537c40ddd7548976a71))

## [0.21.0](https://github.com/Jayphen/homeclaw/compare/v0.20.0...v0.21.0) (2026-03-24)


### Features

* add delivery targeting for routines ([#95](https://github.com/Jayphen/homeclaw/issues/95)) ([d0801b6](https://github.com/Jayphen/homeclaw/commit/d0801b6f2e396841015bd27430961ed15f8da8d2))
* merge household_share into memory_save and add admin tool log ([#97](https://github.com/Jayphen/homeclaw/issues/97)) ([9b88fa4](https://github.com/Jayphen/homeclaw/commit/9b88fa454929cdc23fa14ff49757baddc5776562))

## [0.20.0](https://github.com/Jayphen/homeclaw/compare/v0.19.0...v0.20.0) (2026-03-24)


### Features

* **ui:** add .env editor for plugins ([#91](https://github.com/Jayphen/homeclaw/issues/91)) ([5e8f084](https://github.com/Jayphen/homeclaw/commit/5e8f0847adcd78864a734f86f0887af272860e1b))


### Bug Fixes

* **ci:** allow Claude to read files during code review ([#92](https://github.com/Jayphen/homeclaw/issues/92)) ([9c6335f](https://github.com/Jayphen/homeclaw/commit/9c6335f0dba88cd96eb08859e87c894b1937518b))

## [0.19.0](https://github.com/Jayphen/homeclaw/compare/v0.18.0...v0.19.0) (2026-03-24)


### Features

* **ui:** separate Skills and Plugins into distinct nav items ([#85](https://github.com/Jayphen/homeclaw/issues/85)) ([40a5f27](https://github.com/Jayphen/homeclaw/commit/40a5f27c8de2132a2ede5cb976adca1990a78f54))


### Bug Fixes

* **ci:** grant pull-requests write permission to Claude code review ([#90](https://github.com/Jayphen/homeclaw/issues/90)) ([85e6c5f](https://github.com/Jayphen/homeclaw/commit/85e6c5fca5c38ab0c073c9d758bc407554eff35e))
* deliver routine output via scheduler instead of relying on LLM ([#88](https://github.com/Jayphen/homeclaw/issues/88)) ([03e4b0e](https://github.com/Jayphen/homeclaw/commit/03e4b0e9985c27f8a497a8031dae0a8858ea7d8e))
* don't advance consolidation pointer on parse failure ([#89](https://github.com/Jayphen/homeclaw/issues/89)) ([bba4b7e](https://github.com/Jayphen/homeclaw/commit/bba4b7e29590f243636beecc211b69e17e3ace48))

## [0.18.0](https://github.com/Jayphen/homeclaw/compare/v0.17.0...v0.18.0) (2026-03-24)


### Features

* add Brave, Exa, SearXNG, and Firecrawl web provider plugins ([#82](https://github.com/Jayphen/homeclaw/issues/82)) ([6204a8a](https://github.com/Jayphen/homeclaw/commit/6204a8ae7c37a93ce0a8d7b5ba35f9d17011e1d1))

## [0.17.0](https://github.com/Jayphen/homeclaw/compare/v0.16.1...v0.17.0) (2026-03-24)


### Features

* add Claude Code PR review workflow ([#78](https://github.com/Jayphen/homeclaw/issues/78)) ([7716f7d](https://github.com/Jayphen/homeclaw/commit/7716f7dddd5d26c3a91f5ddd49581a6fab0a1e11))
* add primary/fallback providers for web_search ([e64afef](https://github.com/Jayphen/homeclaw/commit/e64afeff533031434b9aee9082c3a7dd06f7c503))
* pluggable web search/read provider system ([#79](https://github.com/Jayphen/homeclaw/issues/79)) ([2299ad0](https://github.com/Jayphen/homeclaw/commit/2299ad088735747031bb0f275051d45683cd5de7))
* plugins can register custom web search/read providers ([#81](https://github.com/Jayphen/homeclaw/issues/81)) ([c6290fa](https://github.com/Jayphen/homeclaw/commit/c6290faf6fdcceabf2b882938c8f747022f61eb3))


### Bug Fixes

* remove deprecated --no-install flag from uv lock in CI ([65ef4d5](https://github.com/Jayphen/homeclaw/commit/65ef4d5dfb7f8774e7d5b64ea6bec96e291a3a33))
* routines now deliver results via message_send ([7db381e](https://github.com/Jayphen/homeclaw/commit/7db381eda4e85e532d13031763c543ed71ac763b))

## [0.16.1](https://github.com/Jayphen/homeclaw/compare/v0.16.0...v0.16.1) (2026-03-23)


### Bug Fixes

* include household knowledge in all web UI endpoints ([278d0ad](https://github.com/Jayphen/homeclaw/commit/278d0adf0bc2b816ad229dad9b553c4e2c49af3a))
* keep uv.lock in sync with release-please version bumps ([58f2f7b](https://github.com/Jayphen/homeclaw/commit/58f2f7bfdc426a39c46b59a151c054cfb21f1588))

## [0.16.0](https://github.com/Jayphen/homeclaw/compare/v0.15.1...v0.16.0) (2026-03-23)


### Features

* add /api/health endpoint with Docker HEALTHCHECK ([65bdb4b](https://github.com/Jayphen/homeclaw/commit/65bdb4bbd832da4f54ef4becedd8e88480704d25))
* add docs site with SvelteKit + mdsvex ([#74](https://github.com/Jayphen/homeclaw/issues/74)) ([c7652af](https://github.com/Jayphen/homeclaw/commit/c7652af4e7905b710a0a584adce48353f490d8b5))
* add web_read provider settings to web UI ([af8820f](https://github.com/Jayphen/homeclaw/commit/af8820fa17782744e1c2adda457fc22ba0616a47))
* enforce data isolation for read tools in DMs ([b7e3196](https://github.com/Jayphen/homeclaw/commit/b7e31961ae70a018fb86b4086de0356add506496))
* show system health status in Settings &gt; General tab ([d18f73e](https://github.com/Jayphen/homeclaw/commit/d18f73e280f0aa09efc6453d0d802f3ab6ce1681))


### Bug Fixes

* eliminate state drift across config, tool schemas, and channel adapters ([45cd5df](https://github.com/Jayphen/homeclaw/commit/45cd5dfe38708dc38015a49aa94b40a25c0a8516))
* improve interaction_log reliability in system prompt and contact list ([9fca850](https://github.com/Jayphen/homeclaw/commit/9fca850de8aa526fb654cb8bb6e229c36957c9a3))
* resolve svelte-check errors in App.svelte and Skills.svelte ([39fd102](https://github.com/Jayphen/homeclaw/commit/39fd102c9f93ab9101419ff89b31cf70444bd039))
* run svelte-kit sync before build to silence tsconfig warning ([c3a75a9](https://github.com/Jayphen/homeclaw/commit/c3a75a927d443e6ccda5d09818d03d61605ad84d))

## [0.15.1](https://github.com/Jayphen/homeclaw/compare/v0.15.0...v0.15.1) (2026-03-22)


### Bug Fixes

* detect WhatsApp group images by mimetype instead of url ([1730d43](https://github.com/Jayphen/homeclaw/commit/1730d436ea3e50354a42a2fc0a4293235b6abc23))

## [0.15.0](https://github.com/Jayphen/homeclaw/compare/v0.14.0...v0.15.0) (2026-03-22)


### Features

* add Tavily Extract as web_read fallback provider ([e953741](https://github.com/Jayphen/homeclaw/commit/e953741128fe0da56bbf1bbca985a3143222d97a))


### Bug Fixes

* coerce string tags in bookmark_save and hand off vision→fast ([279d839](https://github.com/Jayphen/homeclaw/commit/279d83958079d93f81d8336f408b6bd4a529445f))
* web_search description tells LLM to follow up with web_read ([0d43fab](https://github.com/Jayphen/homeclaw/commit/0d43fab6e913f8da904abb1888fe369946e58876))

## [0.14.0](https://github.com/Jayphen/homeclaw/compare/v0.13.0...v0.14.0) (2026-03-22)


### Features

* add debug info panel to web chat ([0f9be04](https://github.com/Jayphen/homeclaw/commit/0f9be0472971dbdf4808e1453c4a6b337d77b7e4))
* add web UI chat channel ([1f6f1da](https://github.com/Jayphen/homeclaw/commit/1f6f1da2d44c78396b5fd006c575b8d4b9f55a3a))
* hot-reload LLM providers when settings change ([78265cc](https://github.com/Jayphen/homeclaw/commit/78265cc59013f41a29537174b94430cabdc6c2bc))


### Bug Fixes

* always init agent loop in serve command when provider is configured ([047e52a](https://github.com/Jayphen/homeclaw/commit/047e52a20f4770d5bac056adcc90542d5c0239d3))
* apply provider_mode to config on save ([3eade7a](https://github.com/Jayphen/homeclaw/commit/3eade7a346a281dcde8808eeb541f72a318cf12a))
* correctly format prepareSendMessagesRequest return value ([0fc97d1](https://github.com/Jayphen/homeclaw/commit/0fc97d108d1df751c6c3ad7ba2433f373116fdbd))
* hot-update note_detail_level without restart ([92a7094](https://github.com/Jayphen/homeclaw/commit/92a7094a14bc9477ff57f0a713eac984ba924404))
* persist chat history across navigation and page refresh ([7515396](https://github.com/Jayphen/homeclaw/commit/75153960ad52fa01f034ae92059b2b4a2fa65582))
* robust history sanitizer for missing tool results ([167f14f](https://github.com/Jayphen/homeclaw/commit/167f14f807084e654b489730bf47314c4b84bf02))
* sanitize history to prevent orphaned tool results ([60a6a6c](https://github.com/Jayphen/homeclaw/commit/60a6a6cd50f619354ef1ff2c800141e1860ec2f2))
* strip content from web_search results, return structured metadata only ([b6f8bdf](https://github.com/Jayphen/homeclaw/commit/b6f8bdfb3efbc403491323d172968a42013e05c1))

## [0.13.0](https://github.com/Jayphen/homeclaw/compare/v0.12.0...v0.13.0) (2026-03-22)


### Features

* add LLM-summarised tool use events to activity feed ([15fcfff](https://github.com/Jayphen/homeclaw/commit/15fcfff9dac95f5a5205ceb31d393dfcc0570bd4))
* add vision provider for image input routing ([f93cff0](https://github.com/Jayphen/homeclaw/commit/f93cff095e5feddbbbfc8c7fb81387691df3c345))
* add vision provider settings to web UI ([ca986d9](https://github.com/Jayphen/homeclaw/commit/ca986d9e901d5aee72ed69999da739019afb09f8))
* persist provider_mode (simple/advanced) in config ([5f38f8f](https://github.com/Jayphen/homeclaw/commit/5f38f8fe8a93b427aa5fcc0c528826409f77478c))
* redesign settings with tab navigation and simple/advanced LLM provider ([3a80f17](https://github.com/Jayphen/homeclaw/commit/3a80f17017bd8f995fff3c5f1cfe133b6f1bc1f1))
* support multi-skill GitHub repos for skill install ([b627d8b](https://github.com/Jayphen/homeclaw/commit/b627d8bc05afdc572dc73b9005a55986fc474539))


### Bug Fixes

* add 'Same as main' placeholder to fast model input ([6c299af](https://github.com/Jayphen/homeclaw/commit/6c299af65ab3f3d9bd52b6469e3067bad4eed111))
* add Anthropic preset to base URL options in advanced mode ([e421501](https://github.com/Jayphen/homeclaw/commit/e421501d0cc70a786190ee953190cc4b95621a76))
* use consistent 'Same as main' placeholder for vision model ([8d2396d](https://github.com/Jayphen/homeclaw/commit/8d2396dc3e161e01eb790cdc8c875d431ac9624e))
* use consistent base URL presets across main, fast, and vision sections ([708ff07](https://github.com/Jayphen/homeclaw/commit/708ff07301707d55be025f7b89723e1b001d26e9))
* use explicit Anthropic base URL in preset ([fb06601](https://github.com/Jayphen/homeclaw/commit/fb0660159c60656bc3c6b0b24151050a0019b464))


### Documentation

* overhaul README with openclaw comparison, web-UI-first setup, and real status ([f8ae706](https://github.com/Jayphen/homeclaw/commit/f8ae7061723f9f58f72635a26d0107d1a337f566))

## [0.12.0](https://github.com/Jayphen/homeclaw/compare/v0.11.1...v0.12.0) (2026-03-22)


### Features

* add model tag to tool result log lines ([02a53a9](https://github.com/Jayphen/homeclaw/commit/02a53a90118f53ce530735211a26af1ffc107181))
* auto-activate skill instructions on first tool use ([11210e3](https://github.com/Jayphen/homeclaw/commit/11210e3e8a73be689687a14ca89c34d87d9ee80e))
* show model name tag in log viewer ([cdd72eb](https://github.com/Jayphen/homeclaw/commit/cdd72eb863c78e0d8eac01ef211e7fa1a36694e2))
* skip agent response in group chats when [@mentioning](https://github.com/mentioning) someone else ([4fa4e16](https://github.com/Jayphen/homeclaw/commit/4fa4e16f6489f04a3d68e5ca7f035dec8b050170))


### Bug Fixes

* align settings buttons and dropdowns with design system ([4b73dcb](https://github.com/Jayphen/homeclaw/commit/4b73dcb340b492d70ca707a495b70c241caae3c9))
* include tracebacks in log UI and silence httpx polling spam ([8d46619](https://github.com/Jayphen/homeclaw/commit/8d46619cce0fb85aeaee18ef13a46fcb4e2e68d2))

## [0.11.1](https://github.com/Jayphen/homeclaw/compare/v0.11.0...v0.11.1) (2026-03-22)


### Bug Fixes

* preserve tool results in conversation history across turns ([56b24ab](https://github.com/Jayphen/homeclaw/commit/56b24ab8bba4471edee20f3239012bb0639fac5b))
* strip stale reasoning blocks from history and prevent impossible provider states ([f83ed47](https://github.com/Jayphen/homeclaw/commit/f83ed4721c7a142fc47d79770384603c9ac9f4b1))

## [0.11.0](https://github.com/Jayphen/homeclaw/compare/v0.10.0...v0.11.0) (2026-03-22)


### Features

* allow full URLs in skill allowed-domains ([2adf32d](https://github.com/Jayphen/homeclaw/commit/2adf32d8552f2f49eeab917dc596dde0a1e13497))
* resolve env vars in skill allowed-domains ([b9ad9fb](https://github.com/Jayphen/homeclaw/commit/b9ad9fbe2c65ba7c02f1534252dfe671952b4010))


### Bug Fixes

* plugins API tests loading real config.json (auth failures) ([801c43c](https://github.com/Jayphen/homeclaw/commit/801c43cb5334cdda55ea9ce95e986f7e72a1d944))

## [0.10.0](https://github.com/Jayphen/homeclaw/compare/v0.9.0...v0.10.0) (2026-03-22)


### Features

* add recent bookmarks card to dashboard ([0f232a1](https://github.com/Jayphen/homeclaw/commit/0f232a18feb330d3c1a85abd2eed62c609a1fdc7))
* add routines API and UI view ([2f904d8](https://github.com/Jayphen/homeclaw/commit/2f904d856b927c3b4ecb3356975ab90ddef7eb33))
* align UI with Digital Conservatory design system ([bdf813f](https://github.com/Jayphen/homeclaw/commit/bdf813f66d65bb7fc97b8684a436d922ce7cae19))
* configurable note-taking detail level and remove misleading search scores ([2368c97](https://github.com/Jayphen/homeclaw/commit/2368c97459c25c9c566abc1675e5e18590c54834))
* merge Skills and Plugins into unified Extensions view ([f421019](https://github.com/Jayphen/homeclaw/commit/f421019f794fdfc95d439fae4e8cbf114d56391d))
* per-model provider config for fast model ([bc59a73](https://github.com/Jayphen/homeclaw/commit/bc59a73b03973eb1b1f4ca3d42cc58c595039acc))
* require confirmation before sharing notes in DMs ([a152fe8](https://github.com/Jayphen/homeclaw/commit/a152fe8768436346f40c78f953b50d78d22f85ec))
* round-trip reasoning/thinking blocks between tool rounds ([dbffd67](https://github.com/Jayphen/homeclaw/commit/dbffd67ebf1c0c4a2bae9a3538a4531cf5b0945d))
* show last routine execution result in routines view ([c75e559](https://github.com/Jayphen/homeclaw/commit/c75e55904987c598a8f64d61aa3dce247e6d7e64))
* support custom base URL for Anthropic provider ([6866fa0](https://github.com/Jayphen/homeclaw/commit/6866fa0c8ff48c9cfaebaa8f8f8d86aff36b4d81))
* support private per-person contact notes ([a21bd8d](https://github.com/Jayphen/homeclaw/commit/a21bd8d650b9d3b69a8837b331fd559c5178f6f8))


### Bug Fixes

* hide empty 'What homeclaw knows' section ([7ad54ba](https://github.com/Jayphen/homeclaw/commit/7ad54ba5524a96df386c66dea4803f87154a2e3b))
* hide empty info card in contact detail view ([cc39cd2](https://github.com/Jayphen/homeclaw/commit/cc39cd24882839e0ee3b59c3852c9f653d97a62c))
* remove fadeUp entrance animations and add contact URL routing ([39437fe](https://github.com/Jayphen/homeclaw/commit/39437fe20a3ed07cd782747d233799a5bcdc9deb))
* repair broken tests (config provider, plugin registry naming) ([4465c4c](https://github.com/Jayphen/homeclaw/commit/4465c4ca293afae54cad62cb3d1f2c794836338a))
* show clean empty state when no contacts exist ([472ab9e](https://github.com/Jayphen/homeclaw/commit/472ab9e7611a95df9559189573c13c26089b6653))
* show skill validation errors instead of 500, with edit access ([ada8839](https://github.com/Jayphen/homeclaw/commit/ada88391f1b65be8f1326a60c45e1c45734f80d9))
* suppress LLM self-talk chains in interim responses ([6cb3d27](https://github.com/Jayphen/homeclaw/commit/6cb3d27c4c330f799e16c2345d4802ba5a0afbc4))

## [0.9.0](https://github.com/Jayphen/homeclaw/compare/v0.8.0...v0.9.0) (2026-03-22)


### Features

* add activity feed and knowledge stats to dashboard ([5e4a0d3](https://github.com/Jayphen/homeclaw/commit/5e4a0d319250fd2d96185dc27677d2ca1222bd39))
* add activity feed and knowledge stats to dashboard ([d2e6fb2](https://github.com/Jayphen/homeclaw/commit/d2e6fb226ee2a0e066b82c6407d678f6dec9c817))
* replace top nav bar with sidebar navigation ([491a0bf](https://github.com/Jayphen/homeclaw/commit/491a0bf59645e19d2b3627cb990e96179ffe7f53))

## [0.8.0](https://github.com/Jayphen/homeclaw/compare/v0.7.2...v0.8.0) (2026-03-22)


### Features

* apply Digital Conservatory design system to entire web UI ([fc9dabe](https://github.com/Jayphen/homeclaw/commit/fc9dabe5093caeaa333549a7f1327a219e85b21e))
* apply Digital Conservatory design system to entire web UI ([9f15d91](https://github.com/Jayphen/homeclaw/commit/9f15d91c4e3ad038aca24498cf14fa9505d3f75b))

## [0.7.2](https://github.com/Jayphen/homeclaw/compare/v0.7.1...v0.7.2) (2026-03-21)


### Bug Fixes

* support authenticated image sources in image_send tool ([6e0d62a](https://github.com/Jayphen/homeclaw/commit/6e0d62ac34b34a769dad8b3895c764774c65a18d))
* support authenticated image sources in image_send tool ([43bde49](https://github.com/Jayphen/homeclaw/commit/43bde49819d52f1ac735f4549262adbd3b61bd5d))

## [0.7.1](https://github.com/Jayphen/homeclaw/compare/v0.7.0...v0.7.1) (2026-03-21)


### Bug Fixes

* log full tool call args, results, and LLM thinking at INFO level ([0d495ef](https://github.com/Jayphen/homeclaw/commit/0d495ef816206496582b4530b9281bdcaef46b92))

## [0.7.0](https://github.com/Jayphen/homeclaw/compare/v0.6.4...v0.7.0) (2026-03-21)


### Features

* add built-in logs skill with admin-only access control ([4b54b6e](https://github.com/Jayphen/homeclaw/commit/4b54b6e07ddfe7a0f96035f4ba9ab543f2c6c727))
* add image_send tool for sending images via Telegram/WhatsApp ([06d2fce](https://github.com/Jayphen/homeclaw/commit/06d2fce4819899c29c916b52ecea9bab2b11d4aa))
* add persistent file logging, agent output logging, and log download ([dfe6db4](https://github.com/Jayphen/homeclaw/commit/dfe6db4b6edc469099239afd8fb78efaa6239a21))


### Bug Fixes

* skill script execution and env var reliability ([7ab33eb](https://github.com/Jayphen/homeclaw/commit/7ab33ebfe7ccd7f1151676dd1b58b8fb8dd1ecd7))

## [0.6.4](https://github.com/Jayphen/homeclaw/compare/v0.6.3...v0.6.4) (2026-03-21)


### Bug Fixes

* support both $VAR and ${VAR} syntax in skill env substitution ([0ff768c](https://github.com/Jayphen/homeclaw/commit/0ff768c213cca77be7e26be5e8b1fb770bdcdfbf))

## [0.6.3](https://github.com/Jayphen/homeclaw/compare/v0.6.2...v0.6.3) (2026-03-21)


### Bug Fixes

* inject skill .env vars into run_skill_script subprocess environment ([28ac992](https://github.com/Jayphen/homeclaw/commit/28ac9926b23b18e661aa87c90d79c55d39019cc6))

## [0.6.2](https://github.com/Jayphen/homeclaw/compare/v0.6.1...v0.6.2) (2026-03-21)


### Bug Fixes

* read .env fresh on every http_call, not just at load time ([5fa6184](https://github.com/Jayphen/homeclaw/commit/5fa61841cff5686c047e9c985d94fda6ea910551))

## [0.6.1](https://github.com/Jayphen/homeclaw/compare/v0.6.0...v0.6.1) (2026-03-21)


### Bug Fixes

* prevent LLM from misplacing .env and truncating skills ([9dd0e79](https://github.com/Jayphen/homeclaw/commit/9dd0e795fb82f72a21a5ae94d3a68f1914932488))
* state drift audit — fix race conditions, missing DM enforcement, and Svelte reactivity bug ([0635696](https://github.com/Jayphen/homeclaw/commit/06356963c24b96e0036f54928e80fbadb77ad27f))

## [0.6.0](https://github.com/Jayphen/homeclaw/compare/v0.5.18...v0.6.0) (2026-03-21)


### Features

* pointer-based context consolidation for long conversations ([274b57e](https://github.com/Jayphen/homeclaw/commit/274b57e2d21dbcd701c3f534900145041e372fc4))
* skill-level .env files with automatic variable substitution ([c17dc99](https://github.com/Jayphen/homeclaw/commit/c17dc9966b334519a2e30db7339e2be11df690a2))


### Bug Fixes

* bump MAX_TOOL_ROUNDS from 10 to 25 for complex skill workflows ([bbd8795](https://github.com/Jayphen/homeclaw/commit/bbd8795b4b426db72536a6d9c2ae6440714de3b2))
* bump MAX_TOOL_ROUNDS to 40 (matches nanobot) ([fe407a1](https://github.com/Jayphen/homeclaw/commit/fe407a16fc1a4c7df56557516e0316d73e71b893))
* make .env files viewable and editable in skill browser ([7430507](https://github.com/Jayphen/homeclaw/commit/7430507a54d024fd9c28d43e4e97230e7cb12fc9))

## [0.5.18](https://github.com/Jayphen/homeclaw/compare/v0.5.17...v0.5.18) (2026-03-21)


### Bug Fixes

* update skill-creator SKILL.md to match actual codebase ([fe48105](https://github.com/Jayphen/homeclaw/commit/fe48105b4164ec70a75e1057642410d4c2b4249f))

## [0.5.17](https://github.com/Jayphen/homeclaw/compare/v0.5.16...v0.5.17) (2026-03-21)


### Features

* interim responses — LLM can update user during tool rounds ([e49c999](https://github.com/Jayphen/homeclaw/commit/e49c9991b739c4c4568ec62a66e6f2603f37bd9a))


### Bug Fixes

* prevent LLM from promising action without calling tools ([66f3821](https://github.com/Jayphen/homeclaw/commit/66f38213c9bcb9d4892cacf4c997cd1437bd4873))

## [0.5.16](https://github.com/Jayphen/homeclaw/compare/v0.5.15...v0.5.16) (2026-03-21)


### Features

* check skill dependencies at install and in detail view ([64fd252](https://github.com/Jayphen/homeclaw/commit/64fd252bd249966cffe6cb253f52218e98c6efbb))
* Docker-aware dependency hints and auto-install on startup ([03ac36c](https://github.com/Jayphen/homeclaw/commit/03ac36c089eac11fc5516ad7ac4f47263590c233))
* skill_edit_file tool for targeted edits without rewriting ([2bf3787](https://github.com/Jayphen/homeclaw/commit/2bf37875fbe1a41bfe465ce5f7768e4568f3c205))
* skill_install accepts gists and arbitrary URLs ([6c9bc9a](https://github.com/Jayphen/homeclaw/commit/6c9bc9a8cd65bb7f3f22a1155ea36bf9cd20ddb8))


### Bug Fixes

* accept nested metadata values in SKILL.md frontmatter ([2a6ae2f](https://github.com/Jayphen/homeclaw/commit/2a6ae2f24aeb22523e0d5d5880c5d3b8191c4212))

## [0.5.15](https://github.com/Jayphen/homeclaw/compare/v0.5.14...v0.5.15) (2026-03-21)


### Features

* skill install from URL, fix file browsing, delete skills ([c23850b](https://github.com/Jayphen/homeclaw/commit/c23850b04751df232bdb8a558a1d524c3a3ca3e0))
* skill settings panel in web UI ([31706cd](https://github.com/Jayphen/homeclaw/commit/31706cdad9cefe432bf57f15084e1ff60f568654))

## [0.5.14](https://github.com/Jayphen/homeclaw/compare/v0.5.13...v0.5.14) (2026-03-21)


### Features

* allow skill http_call to reach LAN services ([3294821](https://github.com/Jayphen/homeclaw/commit/3294821b238958f529419f4e7c6f9e1b2df5d5b4))
* skill browser and file editor in web UI ([05fd53c](https://github.com/Jayphen/homeclaw/commit/05fd53cf10bb7a26973c027f0cca3e185f9ed967))


### Bug Fixes

* use CodeEditor for non-markdown files in skill browser ([4adcb4d](https://github.com/Jayphen/homeclaw/commit/4adcb4d3c4e91a5fac963eaa200fb56dbdb01fbf))

## [0.5.13](https://github.com/Jayphen/homeclaw/compare/v0.5.12...v0.5.13) (2026-03-21)


### Features

* skill approval flow for non-admin users ([df8a56a](https://github.com/Jayphen/homeclaw/commit/df8a56a39d6e447d04a81cfe358ccb7e954e65a5))


### Bug Fixes

* expose skill plugin tools in read_skill and catalog ([a788b8e](https://github.com/Jayphen/homeclaw/commit/a788b8e741bc920666d26d2e58b84df529bafc6c))

## [0.5.12](https://github.com/Jayphen/homeclaw/compare/v0.5.11...v0.5.12) (2026-03-20)


### Features

* adopt AgentSkills SKILL.md format with progressive disclosure ([955df0d](https://github.com/Jayphen/homeclaw/commit/955df0d12c4479f909305382c8cc55e7aca370ad))


### Bug Fixes

* use correct JID server for LID vs phone number users ([0213509](https://github.com/Jayphen/homeclaw/commit/0213509aeaf9479e2b114af30e6a863cd0912fd9))

## [0.5.11](https://github.com/Jayphen/homeclaw/compare/v0.5.10...v0.5.11) (2026-03-20)


### Bug Fixes

* use build_jid for WhatsApp group JID construction ([ea89dfb](https://github.com/Jayphen/homeclaw/commit/ea89dfb293b1289fdfd21cb04e7cbb8189ac0ac6))

## [0.5.10](https://github.com/Jayphen/homeclaw/compare/v0.5.9...v0.5.10) (2026-03-20)


### Bug Fixes

* discover group IDs from channel history dirs instead of separate file ([5c75631](https://github.com/Jayphen/homeclaw/commit/5c75631285fcc375a3068ba16ffd1fa7a42595a8))
* persist known WhatsApp group IDs across restarts ([bee4e1a](https://github.com/Jayphen/homeclaw/commit/bee4e1aace31378ec583955318ad783029736432))

## [0.5.9](https://github.com/Jayphen/homeclaw/compare/v0.5.8...v0.5.9) (2026-03-20)


### Features

* support sending messages to household group chat ([28a01c8](https://github.com/Jayphen/homeclaw/commit/28a01c88457b4f72816baa5f5653273957beeddf))

## [0.5.8](https://github.com/Jayphen/homeclaw/compare/v0.5.7...v0.5.8) (2026-03-20)


### Features

* log group chat exchanges as markdown for semantic recall ([f91b060](https://github.com/Jayphen/homeclaw/commit/f91b060b046bf4bca8bc01b3215929960e13b0a8))


### Bug Fixes

* include homeclaw responses in group chat log for full recall ([438b51f](https://github.com/Jayphen/homeclaw/commit/438b51f84bc8af017baa6ac046a538427c476ac3))
* slim down group chat log — user messages only, daily rotation ([d59a34a](https://github.com/Jayphen/homeclaw/commit/d59a34aba17c17002ffa707c35b5334d7e216e97))

## [0.5.7](https://github.com/Jayphen/homeclaw/compare/v0.5.6...v0.5.7) (2026-03-20)


### Features

* let homeclaw answer questions about itself ([a20b164](https://github.com/Jayphen/homeclaw/commit/a20b164d2a4bf91ff0d5b114eeb5198da3c05153))


### Bug Fixes

* stop asking if user needs anything else ([79bc326](https://github.com/Jayphen/homeclaw/commit/79bc3265145d43e8116464d72e65f7b1505e9c16))

## [0.5.6](https://github.com/Jayphen/homeclaw/compare/v0.5.5...v0.5.6) (2026-03-20)


### Bug Fixes

* improve system prompt tone for smaller models like Gemini Flash ([ff5e364](https://github.com/Jayphen/homeclaw/commit/ff5e364b9d8a000541b313cb8bdcb6fa6c07169f))

## [0.5.5](https://github.com/Jayphen/homeclaw/compare/v0.5.4...v0.5.5) (2026-03-20)


### Features

* convert markdown to WhatsApp formatting in outbound messages ([07ec239](https://github.com/Jayphen/homeclaw/commit/07ec2393a7b2c8cc2db6dfca7010dd257bdf4490))


### Bug Fixes

* address P1/P2 findings from state drift audit ([c00bc40](https://github.com/Jayphen/homeclaw/commit/c00bc40975a34740e2e70a2905d07ee802636643))
* lowercase member names at all API entry points ([081ea9c](https://github.com/Jayphen/homeclaw/commit/081ea9c4a4255a603a538686c9c2f738cf775f6f))
* show actual WhatsApp sender ID in registration prompt ([9feb5b5](https://github.com/Jayphen/homeclaw/commit/9feb5b5be40601a1c2d3286b9210d7b4187a886a))
* support WhatsApp LIDs in allowed users and registration ([bfd92b8](https://github.com/Jayphen/homeclaw/commit/bfd92b8a96c440574cbb204e0fa4dc1d7e2082da))
* use 24-hour time everywhere in the web UI ([e5fcff3](https://github.com/Jayphen/homeclaw/commit/e5fcff30e0c75ffe461c8ae442b8b14462a108b3))

## [0.5.4](https://github.com/Jayphen/homeclaw/compare/v0.5.3...v0.5.4) (2026-03-20)


### Features

* add /register_member admin command, extract shared registration ([915a4ff](https://github.com/Jayphen/homeclaw/commit/915a4ffec3b096316d721bb765b1e44012ef826b))
* auto-register unknown group members from WhatsApp display name ([53f206e](https://github.com/Jayphen/homeclaw/commit/53f206e818172399ece4c392f611e11cba6b1da9))


### Bug Fixes

* store group chat history under household/channels/ ([6bb8370](https://github.com/Jayphen/homeclaw/commit/6bb83705eccd1c85141ccd8708017206be013e49))

## [0.5.3](https://github.com/Jayphen/homeclaw/compare/v0.5.2...v0.5.3) (2026-03-20)


### Bug Fixes

* handle missing url attribute on WhatsApp image message stubs ([5731a52](https://github.com/Jayphen/homeclaw/commit/5731a526c040b295bc9310785a7da28261e62db4))

## [0.5.2](https://github.com/Jayphen/homeclaw/compare/v0.5.1...v0.5.2) (2026-03-20)


### Bug Fixes

* add debug logging and error handling to WhatsApp message handler ([acd658b](https://github.com/Jayphen/homeclaw/commit/acd658ba8bc41b6da92d2e6762c8679093be4387))

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

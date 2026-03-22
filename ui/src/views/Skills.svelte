<script lang="ts">
  import { api } from "$lib/api";
  import { renderMarkdown } from "$lib/markdown";
  import MarkdownEditor from "$lib/MarkdownEditor.svelte";
  import CodeEditor from "$lib/CodeEditor.svelte";

  let { params = {} }: { params?: { owner?: string; name?: string; wild?: string } } = $props();

  // svelte-spa-router passes wildcard paths as params.wild
  const filePath = $derived(params.wild || null);

  interface SkillFile {
    path: string;
    size: string;
  }

  interface SkillEntry {
    name: string;
    owner: string;
    description: string;
    allowed_domains: string[];
    file_count: number;
    files: SkillFile[];
  }

  interface MissingBin {
    name: string;
    hint: string;
  }

  interface SkillDeps {
    missing_bins: MissingBin[];
    missing_env: string[];
    satisfied: boolean;
    runtime: string;
  }

  interface SkillDetail {
    name: string;
    owner: string;
    description: string;
    allowed_domains: string[];
    instructions: string;
    metadata: Record<string, any>;
    compatibility: string | null;
    files: SkillFile[];
    deps: SkillDeps | null;
  }

  interface FileContent {
    path: string;
    content: string;
    size: number;
  }

  let skills: SkillEntry[] = $state([]);
  let detail: SkillDetail | null = $state(null);
  let fileContent: FileContent | null = $state(null);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);
  let editing: boolean = $state(false);
  let editContent: string = $state("");
  let deleting: boolean = $state(false);
  let confirmDelete: boolean = $state(false);
  let saving: boolean = $state(false);

  // Install
  let installUrl: string = $state("");
  let installing: boolean = $state(false);
  let installResult: { status: string; name?: string; error?: string; deps?: { missing_bins: string[]; missing_env: string[] } } | null = $state(null);

  // Settings
  let settingsLoaded: boolean = $state(false);
  let approvalRequired: boolean = $state(true);
  let allowLocalNetwork: boolean = $state(false);
  let savingSettings: boolean = $state(false);

  const mode = $derived.by(() => {
    if (params.owner && params.name && filePath) return "file" as const;
    if (params.owner && params.name) return "detail" as const;
    return "index" as const;
  });

  const groupedByOwner = $derived.by(() => {
    const map = new Map<string, SkillEntry[]>();
    for (const s of skills) {
      const arr = map.get(s.owner) || [];
      arr.push(s);
      map.set(s.owner, arr);
    }
    return map;
  });

  async function fetchSettings() {
    try {
      const r = await api("/api/skills/settings");
      if (!r.ok) return;
      const data = await r.json();
      approvalRequired = data.skill_approval_required;
      allowLocalNetwork = data.skill_allow_local_network;
      settingsLoaded = true;
    } catch { /* ignore — non-admin may not have access */ }
  }

  async function saveSettings(field: string, value: boolean) {
    savingSettings = true;
    try {
      const r = await api("/api/skills/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [field]: value }),
      });
      if (!r.ok) throw new Error(`${r.status}`);
      const data = await r.json();
      approvalRequired = data.skill_approval_required;
      allowLocalNetwork = data.skill_allow_local_network;
    } catch (e: any) {
      error = e.message;
    } finally {
      savingSettings = false;
    }
  }

  async function installFromUrl() {
    if (!installUrl.trim()) return;
    installing = true;
    installResult = null;
    try {
      const r = await api("/api/skills/install", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: installUrl.trim() }),
      });
      const data = await r.json();
      if (!r.ok) {
        installResult = { status: "error", error: data.detail || `HTTP ${r.status}` };
      } else {
        installResult = { status: "installed", name: data.name };
        installUrl = "";
        fetchIndex(); // refresh the list
      }
    } catch (e: any) {
      installResult = { status: "error", error: e.message };
    } finally {
      installing = false;
    }
  }

  async function deleteSkill() {
    if (!params.owner || !params.name) return;
    deleting = true;
    try {
      const r = await api(`/api/skills/${params.owner}/${params.name}`, { method: "DELETE" });
      if (!r.ok) {
        const data = await r.json();
        error = data.detail || `HTTP ${r.status}`;
        deleting = false;
        return;
      }
      // Navigate back to index
      window.location.hash = "#/skills";
    } catch (e: any) {
      error = e.message;
      deleting = false;
    }
  }

  async function fetchIndex() {
    loading = true;
    error = null;
    try {
      const r = await api("/api/skills");
      if (!r.ok) throw new Error(`${r.status}`);
      const data = await r.json();
      skills = data.skills;
      loading = false;
    } catch (e: any) {
      error = e.message;
      loading = false;
    }
  }

  async function fetchDetail(owner: string, name: string) {
    loading = true;
    error = null;
    try {
      const r = await api(`/api/skills/${owner}/${name}`);
      if (!r.ok) throw new Error(`${r.status}`);
      detail = await r.json();
      loading = false;
    } catch (e: any) {
      error = e.message;
      loading = false;
    }
  }

  async function fetchFile(owner: string, name: string, filePath: string) {
    loading = true;
    error = null;
    try {
      const r = await api(`/api/skills/${owner}/${name}/files/${filePath}`);
      if (!r.ok) throw new Error(`${r.status}`);
      fileContent = await r.json();
      loading = false;
    } catch (e: any) {
      error = e.message;
      loading = false;
    }
  }

  function startEdit() {
    if (fileContent) {
      editContent = fileContent.content;
      editing = true;
    }
  }

  function cancelEdit() {
    editing = false;
  }

  async function saveEdit() {
    if (!fileContent || !params.owner || !params.name || !filePath) return;
    saving = true;
    try {
      const r = await api(`/api/skills/${params.owner}/${params.name}/files/${filePath}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: editContent }),
      });
      if (!r.ok) throw new Error(`${r.status}`);
      fileContent = { ...fileContent, content: editContent, size: editContent.length };
      editing = false;
    } catch (e: any) {
      error = e.message;
    } finally {
      saving = false;
    }
  }

  $effect(() => {
    if (mode === "file" && params.owner && params.name && filePath) {
      fetchFile(params.owner, params.name, filePath);
    } else if (mode === "detail" && params.owner && params.name) {
      fetchDetail(params.owner, params.name);
    } else {
      fetchIndex();
      fetchSettings();
    }
  });

  function fileIcon(path: string): string {
    if (path === "SKILL.md") return "📋";
    if (path === ".env") return "🔑";
    if (path.startsWith("data/")) return "📁";
    if (path.startsWith("scripts/")) return "⚙️";
    if (path.startsWith("references/")) return "📖";
    return "📄";
  }

  function isMarkdown(path: string): boolean {
    return path.endsWith(".md");
  }

  const langMap: Record<string, string> = {
    json: "json", yaml: "yaml", yml: "yaml", toml: "toml",
    py: "python", sh: "shell", bash: "shell",
    js: "javascript", ts: "typescript", csv: "csv", txt: "text",
    env: "env",
  };

  function fileLang(path: string): string {
    const ext = path.split(".").pop()?.toLowerCase() ?? "";
    return langMap[ext] || ext;
  }

  function isTextFile(path: string): boolean {
    const name = path.split("/").pop() ?? "";
    // Dotfiles like .env, .gitignore
    if (name.startsWith(".") && !name.includes(".", 1)) return true;
    const ext = name.split(".").pop()?.toLowerCase() ?? "";
    return ["md", "txt", "json", "yaml", "yml", "toml", "py", "sh", "js", "ts", "csv", "env"].includes(ext);
  }
</script>

<div class="skills-page">
  <nav class="breadcrumb">
    <a href="#/skills">Skills</a>
    {#if params.owner && params.name}
      <span class="sep">/</span>
      <a href="#/skills/{params.owner}/{params.name}">{params.name}</a>
      <span class="owner-tag">{params.owner}</span>
    {/if}
    {#if filePath}
      <span class="sep">/</span>
      <span>{filePath}</span>
    {/if}
  </nav>

  {#if loading}
    <div class="loading">
      <div class="loading-dot"></div>
      <div class="loading-dot"></div>
      <div class="loading-dot"></div>
    </div>
  {:else if error}
    <div class="error-card">
      <p>Couldn't load skills.</p>
      <small>{error}</small>
    </div>
  {:else if mode === "file" && fileContent}
    <!-- File view/edit -->
    <article class="file-article">
      <header>
        <h1>{fileContent.path}</h1>
        <span class="file-size">{fileContent.size} bytes</span>
      </header>
      {#if editing}
        <div class="file-editor">
          {#if fileContent.path === "SKILL.md"}
            <CodeEditor bind:value={editContent} disabled={saving} language="yaml+markdown" />
          {:else if isMarkdown(fileContent.path)}
            <MarkdownEditor bind:value={editContent} disabled={saving} />
          {:else}
            <CodeEditor bind:value={editContent} disabled={saving} language={fileLang(fileContent.path)} />
          {/if}
          <div class="editor-actions">
            <button class="btn btn-secondary" onclick={cancelEdit} disabled={saving}>Cancel</button>
            <button class="btn btn-primary" onclick={saveEdit} disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      {:else}
        <div class="file-body">
          <button class="btn-edit" onclick={startEdit}>Edit</button>
          {#if fileContent.path === "SKILL.md"}
            <pre><code>{fileContent.content}</code></pre>
          {:else if fileContent.path.endsWith(".md")}
            {@html renderMarkdown(fileContent.content)}
          {:else}
            <pre><code>{fileContent.content}</code></pre>
          {/if}
        </div>
      {/if}
    </article>
  {:else if mode === "detail" && detail}
    <!-- Skill detail with file list -->
    <div class="skill-header">
      <div class="skill-header-row">
        <h1 class="page-title">{detail.name}</h1>
        {#if confirmDelete}
          <div class="delete-confirm">
            <span>Delete this skill?</span>
            <button class="btn btn-danger" onclick={deleteSkill} disabled={deleting}>
              {deleting ? "Deleting…" : "Yes, archive it"}
            </button>
            <button class="btn btn-secondary" onclick={() => (confirmDelete = false)}>Cancel</button>
          </div>
        {:else}
          <button class="btn-delete" onclick={() => (confirmDelete = true)}>Delete</button>
        {/if}
      </div>
      <p class="skill-desc">{detail.description}</p>
      {#if detail.allowed_domains.length > 0}
        <div class="skill-domains">
          {#each detail.allowed_domains as domain}
            <span class="domain-tag">{domain}</span>
          {/each}
        </div>
      {/if}
      {#if detail.compatibility}
        <p class="skill-compat">{detail.compatibility}</p>
      {/if}
      {#if detail.deps}
        <div class="dep-warnings">
          <p class="dep-heading">Missing dependencies {#if detail.deps.runtime === "docker"}<span class="dep-runtime">Docker</span>{/if}</p>
          {#each detail.deps.missing_bins as bin}
            <div class="dep-item">
              <code>{bin.name}</code>
              <span class="dep-hint">{bin.hint}</span>
            </div>
          {/each}
          {#each detail.deps.missing_env as env}
            <div class="dep-item">
              <code>{env}</code>
              <span class="dep-hint">{detail.deps.runtime === "docker" ? `Set in docker-compose.yml environment or .env file` : `Set in your shell or .env file`}</span>
            </div>
          {/each}
        </div>
      {/if}
    </div>

    <section class="file-section">
      <h2>Files <span class="file-count">{detail.files.length}</span></h2>
      <div class="file-list">
        {#each detail.files as file, i}
          {#if isTextFile(file.path)}
            <a
              class="file-card"
              href="#/skills/{params.owner}/{params.name}/{file.path}"
              style="animation-delay: {i * 30}ms"
            >
              <span class="file-icon">{fileIcon(file.path)}</span>
              <span class="file-path">{file.path}</span>
              <span class="file-size">{file.size} B</span>
            </a>
          {:else}
            <div class="file-card file-card-disabled" style="animation-delay: {i * 30}ms">
              <span class="file-icon">{fileIcon(file.path)}</span>
              <span class="file-path">{file.path}</span>
              <span class="file-size">{file.size} B</span>
            </div>
          {/if}
        {/each}
      </div>
    </section>

    {#if detail.instructions}
      <section class="instructions-section">
        <h2>Instructions</h2>
        <div class="instructions-body">
          {@html renderMarkdown(detail.instructions)}
        </div>
      </section>
    {/if}
  {:else}
    <!-- Index: all skills grouped by owner -->
    <h1 class="page-title">Skills</h1>

    {#if settingsLoaded}
      <section class="settings-panel">
        <h2>Settings</h2>
        <label class="toggle-row">
          <span class="toggle-label">
            <strong>Require admin approval</strong>
            <small>Non-admins need approval before skills go live</small>
          </span>
          <input
            type="checkbox"
            class="toggle"
            checked={approvalRequired}
            disabled={savingSettings}
            onchange={(e) => saveSettings("skill_approval_required", e.currentTarget.checked)}
          />
        </label>
        <label class="toggle-row">
          <span class="toggle-label">
            <strong>Allow local network</strong>
            <small>Let skills reach LAN services (Home Assistant, etc.)</small>
          </span>
          <input
            type="checkbox"
            class="toggle"
            checked={allowLocalNetwork}
            disabled={savingSettings}
            onchange={(e) => saveSettings("skill_allow_local_network", e.currentTarget.checked)}
          />
        </label>
      </section>
    {/if}

    <section class="install-panel">
      <h2>Install from URL</h2>
      <form class="install-form" onsubmit={(e) => { e.preventDefault(); installFromUrl(); }}>
        <input
          type="url"
          class="install-input"
          bind:value={installUrl}
          placeholder="https://github.com/user/skill-name or direct SKILL.md URL"
          disabled={installing}
        />
        <button class="btn btn-primary" type="submit" disabled={installing || !installUrl.trim()}>
          {installing ? "Installing…" : "Install"}
        </button>
      </form>
      {#if installResult}
        {#if installResult.status === "installed"}
          <p class="install-success">Installed <strong>{installResult.name}</strong></p>
          {#if installResult.deps}
            <div class="dep-warnings">
              {#each installResult.deps.missing_bins as bin}
                <div class="dep-item"><code>{bin.name}</code> <span class="dep-hint">{bin.hint}</span></div>
              {/each}
              {#each installResult.deps.missing_env as env}
                <div class="dep-item"><code>{env}</code> <span class="dep-hint">Set in your environment or .env file</span></div>
              {/each}
            </div>
          {/if}
        {:else}
          <p class="install-error">{installResult.error}</p>
        {/if}
      {/if}
    </section>

    {#if skills.length === 0}
      <div class="empty">
        <p>No skills yet.</p>
        <small>Chat with homeclaw to create skills for your household.</small>
      </div>
    {:else}
      {#each [...groupedByOwner.entries()] as [owner, ownerSkills], gi}
        <section class="owner-section" style="animation-delay: {gi * 60}ms">
          <h2>{owner} <span class="skill-count">{ownerSkills.length}</span></h2>
          <div class="skill-list">
            {#each ownerSkills as skill, i}
              <a
                class="skill-card"
                href="#/skills/{skill.owner}/{skill.name}"
                style="animation-delay: {(gi * 60) + (i * 40)}ms"
              >
                <div class="skill-card-header">
                  <span class="skill-card-name">{skill.name}</span>
                  <span class="skill-card-files">{skill.file_count} files</span>
                </div>
                <div class="skill-card-desc">{skill.description}</div>
                {#if skill.allowed_domains.length > 0}
                  <div class="skill-card-domains">
                    {#each skill.allowed_domains as domain}
                      <span class="domain-tag-sm">{domain}</span>
                    {/each}
                  </div>
                {/if}
              </a>
            {/each}
          </div>
        </section>
      {/each}
    {/if}
  {/if}
</div>

<style>
  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .skills-page { animation: fadeUp 0.35s ease-out; }

  /* Settings panel */
  .settings-panel {
    background: var(--surface);
    border-radius: var(--radius); padding: 1rem 1.25rem; margin-bottom: 1.5rem;
  }
  .settings-panel h2 {
    font-family: var(--font-serif); font-weight: 600; font-size: 1rem;
    margin: 0 0 0.75rem; color: var(--text);
  }
  .toggle-row {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0.5rem 0; cursor: pointer;
  }
  .toggle-row + .toggle-row { }
  .toggle-label { display: flex; flex-direction: column; gap: 0.1rem; }
  .toggle-label strong { font-size: 0.85rem; font-weight: 600; color: var(--text); }
  .toggle-label small { font-size: 0.75rem; color: var(--text-muted); }
  .toggle {
    width: 38px; height: 22px; appearance: none; -webkit-appearance: none;
    background: #d4cfc9; border-radius: 11px; position: relative;
    cursor: pointer; transition: background 0.2s; flex-shrink: 0;
  }
  .toggle::after {
    content: ""; position: absolute; top: 2px; left: 2px;
    width: 18px; height: 18px; border-radius: 50%;
    background: white; transition: transform 0.2s; box-shadow: 0 1px 2px rgba(28, 28, 23, 0.15);
  }
  .toggle:checked { background: var(--sage); }
  .toggle:checked::after { transform: translateX(16px); }
  .toggle:disabled { opacity: 0.5; cursor: not-allowed; }

  /* Delete */
  .btn-delete {
    background: var(--surface-low); border: none; border-radius: var(--radius-pill);
    padding: 0.3rem 0.75rem; font-size: 0.78rem; color: var(--text-muted);
    cursor: pointer; transition: background 0.15s, color 0.15s;
  }
  .btn-delete:hover { background: var(--primary); color: #fff; }
  .delete-confirm { display: flex; align-items: center; gap: 0.5rem; font-size: 0.82rem; }
  .delete-confirm span { color: var(--text-muted); }
  .btn-danger {
    background: var(--rose, #c44); border: none; color: #fff;
    padding: 0.3rem 0.75rem; border-radius: var(--radius-pill); font-size: 0.78rem; cursor: pointer;
  }
  .btn-danger:hover:not(:disabled) { opacity: 0.9; }
  .btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }

  /* Install panel */
  .install-panel {
    background: var(--surface);
    border-radius: var(--radius); padding: 1rem 1.25rem; margin-bottom: 1.5rem;
  }
  .install-panel h2 {
    font-family: var(--font-serif); font-weight: 600; font-size: 1rem;
    margin: 0 0 0.75rem; color: var(--text);
  }
  .install-form { display: flex; gap: 0.5rem; }
  .install-input {
    flex: 1; padding: 0.45rem 0.75rem; border: 1px solid var(--border);
    border-radius: var(--radius-md); font-size: 0.85rem; color: var(--text);
    background: var(--bg); outline: none;
  }
  .install-input:focus { border-color: var(--primary); }
  .install-input::placeholder { color: var(--text-muted); opacity: 0.7; }
  .install-success { color: var(--sage); font-size: 0.82rem; margin: 0.5rem 0 0; }
  .install-error { color: var(--rose, #c44); font-size: 0.82rem; margin: 0.5rem 0 0; }
  .dep-warnings {
    background: #fef8ee; border-radius: var(--radius);
    padding: 0.6rem 0.85rem; margin-top: 0.5rem; font-size: 0.8rem; color: #8a6d3b;
  }
  .dep-heading { margin: 0 0 0.4rem; font-weight: 600; }
  .dep-runtime {
    font-size: 0.68rem; font-weight: 600; background: #e8dcc8; color: #6b563e;
    padding: 0.1rem 0.35rem; border-radius: var(--radius-sm); margin-left: 0.3rem; vertical-align: middle;
  }
  .dep-item { padding: 0.25rem 0; display: flex; flex-direction: column; gap: 0.1rem; }
  .dep-item + .dep-item { }
  .dep-item code { background: rgba(28, 28, 23, 0.05); padding: 0.1rem 0.3rem; border-radius: var(--radius-sm); width: fit-content; }
  .dep-hint { font-size: 0.75rem; color: #a08050; }
  .skill-compat { font-size: 0.8rem; color: var(--text-muted); margin: 0.3rem 0 0; font-style: italic; }

  /* Breadcrumb */
  .breadcrumb { display: flex; align-items: center; gap: 0.35rem; margin-bottom: 1rem; font-size: 0.82rem; }
  .breadcrumb a { color: var(--primary); text-decoration: none; }
  .breadcrumb a:hover { text-decoration: underline; }
  .breadcrumb span { color: var(--text-muted); }
  .sep { color: var(--border); }
  .owner-tag {
    font-size: 0.7rem; font-weight: 600; color: var(--primary);
    background: var(--surface-low); padding: 0.1rem 0.4rem; border-radius: var(--radius-sm); margin-left: 0.3rem;
  }

  /* Page title */
  .page-title {
    font-family: var(--font-serif); font-weight: 600; font-size: 1.6rem;
    margin: 0 0 1.25rem; letter-spacing: -0.02em; color: var(--text);
  }

  /* Owner sections */
  .owner-section { margin-bottom: 2rem; opacity: 0; animation: fadeUp 0.3s ease-out forwards; }
  .owner-section h2 {
    font-family: var(--font-serif); font-weight: 600; font-size: 1.1rem;
    margin: 0 0 0.75rem; display: flex; align-items: center; gap: 0.5rem;
    text-transform: capitalize;
  }
  .skill-count, .file-count {
    font-family: var(--font-sans); font-size: 0.72rem; font-weight: 600;
    color: var(--text-muted); background: var(--surface-low); padding: 0.1rem 0.45rem; border-radius: var(--radius-sm);
  }

  /* Skill cards (index) */
  .skill-list { display: flex; flex-direction: column; gap: 0.5rem; }
  .skill-card {
    display: block; padding: 0.75rem 1rem; background: var(--surface);
    border-radius: var(--radius);
    text-decoration: none; color: var(--text);
    transition: background 0.15s;
    opacity: 0; animation: fadeUp 0.3s ease-out forwards;
  }
  .skill-card:hover { background: var(--surface-low); box-shadow: inset 0 0 0 1px rgba(198, 200, 184, 0.2); }
  .skill-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem; }
  .skill-card-name { font-weight: 600; font-size: 0.9rem; }
  .skill-card-files { font-size: 0.72rem; color: var(--text-muted); }
  .skill-card-desc { font-size: 0.82rem; color: var(--text-muted); line-height: 1.4; }
  .skill-card-domains { margin-top: 0.4rem; display: flex; gap: 0.3rem; flex-wrap: wrap; }
  .domain-tag-sm {
    font-size: 0.68rem; background: var(--surface-low); color: var(--primary);
    padding: 0.1rem 0.35rem; border-radius: var(--radius-sm);
  }

  /* Skill detail header */
  .skill-header { margin-bottom: 1.5rem; }
  .skill-header-row { display: flex; align-items: center; justify-content: space-between; }
  .skill-header .page-title { margin-bottom: 0.25rem; }
  .skill-desc { font-size: 0.9rem; color: var(--text-muted); margin: 0 0 0.5rem; }
  .skill-domains { display: flex; gap: 0.4rem; flex-wrap: wrap; }
  .domain-tag {
    font-size: 0.75rem; background: var(--surface-low); color: var(--primary);
    padding: 0.15rem 0.5rem; border-radius: var(--radius-sm); font-weight: 500;
  }

  /* File list (detail view) */
  .file-section { margin-bottom: 2rem; }
  .file-section h2 {
    font-family: var(--font-serif); font-weight: 600; font-size: 1.1rem;
    margin: 0 0 0.75rem; display: flex; align-items: center; gap: 0.5rem;
  }
  .file-list { display: flex; flex-direction: column; gap: 0.35rem; }
  .file-card {
    display: flex; align-items: center; gap: 0.6rem;
    padding: 0.55rem 0.85rem; background: var(--surface);
    border-radius: var(--radius-md);
    text-decoration: none; color: var(--text); font-size: 0.85rem;
    transition: background 0.15s;
    opacity: 0; animation: fadeUp 0.3s ease-out forwards;
  }
  .file-card:hover:not(.file-card-disabled) { background: var(--surface-low); }
  .file-card-disabled { opacity: 0.6; cursor: default; }
  .file-icon { flex-shrink: 0; }
  .file-path { flex: 1; font-family: monospace; font-size: 0.82rem; }
  .file-size { font-size: 0.72rem; color: var(--text-muted); flex-shrink: 0; }

  /* Instructions preview */
  .instructions-section {
    background: var(--surface);
    border-radius: var(--radius); padding: 1.25rem 1.5rem;
  }
  .instructions-section h2 {
    font-family: var(--font-serif); font-weight: 600; font-size: 1.1rem; margin: 0 0 0.75rem;
  }
  .instructions-body { font-size: 0.88rem; line-height: 1.6; color: var(--text); }
  .instructions-body :global(h1), .instructions-body :global(h2), .instructions-body :global(h3) {
    font-family: var(--font-serif); margin: 1rem 0 0.4rem;
  }
  .instructions-body :global(h2) { font-size: 1rem; }
  .instructions-body :global(p) { margin: 0.4rem 0; }
  .instructions-body :global(ul), .instructions-body :global(ol) { margin: 0.4rem 0; padding-left: 1.5rem; }
  .instructions-body :global(code) { background: var(--surface-low); padding: 0.1rem 0.3rem; border-radius: var(--radius-sm); font-size: 0.85em; }

  /* File article (file view/edit) */
  .file-article {
    background: var(--surface);
    border-radius: var(--radius); padding: 1.5rem 2rem;
  }
  .file-article header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 1rem; padding-bottom: 0.75rem;
  }
  .file-article h1 {
    font-family: monospace; font-weight: 600; font-size: 1rem; margin: 0; color: var(--text);
  }
  .file-article .file-size { font-size: 0.75rem; color: var(--text-muted); }
  .file-body { font-size: 0.9rem; line-height: 1.6; }
  .file-body pre {
    background: var(--surface-low); padding: 1rem; border-radius: var(--radius);
    overflow-x: auto; font-size: 0.82rem;
  }
  .file-body :global(h1), .file-body :global(h2), .file-body :global(h3) { font-family: var(--font-serif); margin: 1rem 0 0.4rem; }
  .file-body :global(p) { margin: 0.4rem 0; }
  .file-body :global(ul), .file-body :global(ol) { margin: 0.4rem 0; padding-left: 1.5rem; }
  .file-body :global(code) { background: var(--surface-low); padding: 0.1rem 0.3rem; border-radius: var(--radius-sm); font-size: 0.85em; }
  .file-body :global(a) { color: var(--primary); }

  /* Edit button & editor */
  .btn-edit {
    float: right; background: var(--surface-low); border: none;
    border-radius: var(--radius-pill); padding: 0.3rem 0.75rem;
    font-size: 0.78rem; color: var(--text-muted); cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }
  .btn-edit:hover { background: var(--primary); color: #fff; }
  .file-editor { display: flex; flex-direction: column; gap: 0.75rem; }
  .editor-actions { display: flex; justify-content: flex-end; gap: 0.5rem; }
  .btn {
    padding: 0.4rem 1rem; border-radius: var(--radius);
    font-size: 0.82rem; font-weight: 500; cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
  }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-secondary { background: var(--surface-low); border: none; color: var(--text-muted); border-radius: var(--radius-pill); }
  .btn-secondary:hover:not(:disabled) { color: var(--text); }
  .btn-primary { background: var(--primary); border: none; color: #fff; border-radius: var(--radius-pill); }
  .btn-primary:hover:not(:disabled) { opacity: 0.9; }

  /* Empty & loading */
  .empty { text-align: center; padding: 3rem 1rem; color: var(--text-muted); }
  .empty p { font-family: var(--font-serif); font-style: italic; font-size: 1.1rem; margin: 0 0 0.5rem; }
  .empty small { font-size: 0.82rem; }
  .loading { display: flex; justify-content: center; gap: 0.5rem; padding: 4rem 0; }
  .loading-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--primary); opacity: 0.3;
    animation: pulse 1s ease-in-out infinite;
  }
  .loading-dot:nth-child(2) { animation-delay: 0.15s; }
  .loading-dot:nth-child(3) { animation-delay: 0.3s; }
  @keyframes pulse {
    0%, 100% { opacity: 0.3; transform: scale(1); }
    50% { opacity: 1; transform: scale(1.2); }
  }
  .error-card {
    background: var(--surface-low); border: none;
    border-radius: var(--radius); padding: 1.5rem; text-align: center; color: var(--secondary);
  }
  .error-card p { margin: 0 0 0.5rem; font-weight: 500; }
  .error-card small { color: var(--text-muted); }

  @media (max-width: 640px) {
    .file-article { padding: 1rem 1.25rem; }
  }
</style>

<script lang="ts">
  import { api } from "$lib/api";
  import { renderMarkdown } from "$lib/markdown";
  import MarkdownEditor from "$lib/MarkdownEditor.svelte";
  import CodeEditor from "$lib/CodeEditor.svelte";

  let { params = {} }: { params?: { owner?: string; name?: string; file?: string } } = $props();

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

  interface SkillDetail {
    name: string;
    owner: string;
    description: string;
    allowed_domains: string[];
    instructions: string;
    metadata: Record<string, string>;
    files: SkillFile[];
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
  let saving: boolean = $state(false);

  const mode = $derived.by(() => {
    if (params.owner && params.name && params.file) return "file" as const;
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
    if (!fileContent || !params.owner || !params.name || !params.file) return;
    saving = true;
    try {
      const r = await api(`/api/skills/${params.owner}/${params.name}/files/${params.file}`, {
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
    if (mode === "file" && params.owner && params.name && params.file) {
      fetchFile(params.owner, params.name, params.file);
    } else if (mode === "detail" && params.owner && params.name) {
      fetchDetail(params.owner, params.name);
    } else {
      fetchIndex();
    }
  });

  function fileIcon(path: string): string {
    if (path === "SKILL.md") return "📋";
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
  };

  function fileLang(path: string): string {
    const ext = path.split(".").pop()?.toLowerCase() ?? "";
    return langMap[ext] || ext;
  }

  function isTextFile(path: string): boolean {
    const ext = path.split(".").pop()?.toLowerCase() ?? "";
    return ["md", "txt", "json", "yaml", "yml", "toml", "py", "sh", "js", "ts", "csv"].includes(ext);
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
    {#if params.file}
      <span class="sep">/</span>
      <span>{params.file}</span>
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
          {#if isMarkdown(fileContent.path)}
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
          {#if fileContent.path.endsWith(".md")}
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
      <h1 class="page-title">{detail.name}</h1>
      <p class="skill-desc">{detail.description}</p>
      {#if detail.allowed_domains.length > 0}
        <div class="skill-domains">
          {#each detail.allowed_domains as domain}
            <span class="domain-tag">{domain}</span>
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

  /* Breadcrumb */
  .breadcrumb { display: flex; align-items: center; gap: 0.35rem; margin-bottom: 1rem; font-size: 0.82rem; }
  .breadcrumb a { color: var(--terracotta); text-decoration: none; }
  .breadcrumb a:hover { text-decoration: underline; }
  .breadcrumb span { color: var(--text-muted); }
  .sep { color: var(--border); }
  .owner-tag {
    font-size: 0.7rem; font-weight: 600; color: var(--sage);
    background: #f0ebe5; padding: 0.1rem 0.4rem; border-radius: 4px; margin-left: 0.3rem;
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
    color: var(--text-muted); background: #f0ebe5; padding: 0.1rem 0.45rem; border-radius: 4px;
  }

  /* Skill cards (index) */
  .skill-list { display: flex; flex-direction: column; gap: 0.5rem; }
  .skill-card {
    display: block; padding: 0.75rem 1rem; background: var(--surface);
    border: 1px solid var(--border); border-radius: var(--radius);
    text-decoration: none; color: var(--text);
    transition: border-color 0.15s, background 0.15s;
    opacity: 0; animation: fadeUp 0.3s ease-out forwards;
  }
  .skill-card:hover { border-color: var(--terracotta); background: #fef9f4; }
  .skill-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem; }
  .skill-card-name { font-weight: 600; font-size: 0.9rem; }
  .skill-card-files { font-size: 0.72rem; color: var(--text-muted); }
  .skill-card-desc { font-size: 0.82rem; color: var(--text-muted); line-height: 1.4; }
  .skill-card-domains { margin-top: 0.4rem; display: flex; gap: 0.3rem; flex-wrap: wrap; }
  .domain-tag-sm {
    font-size: 0.68rem; background: #e8f4e8; color: var(--sage);
    padding: 0.1rem 0.35rem; border-radius: 3px;
  }

  /* Skill detail header */
  .skill-header { margin-bottom: 1.5rem; }
  .skill-header .page-title { margin-bottom: 0.25rem; }
  .skill-desc { font-size: 0.9rem; color: var(--text-muted); margin: 0 0 0.5rem; }
  .skill-domains { display: flex; gap: 0.4rem; flex-wrap: wrap; }
  .domain-tag {
    font-size: 0.75rem; background: #e8f4e8; color: var(--sage);
    padding: 0.15rem 0.5rem; border-radius: 4px; font-weight: 500;
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
    border: 1px solid var(--border); border-radius: var(--radius);
    text-decoration: none; color: var(--text); font-size: 0.85rem;
    transition: border-color 0.15s;
    opacity: 0; animation: fadeUp 0.3s ease-out forwards;
  }
  .file-card:hover:not(.file-card-disabled) { border-color: var(--terracotta); }
  .file-card-disabled { opacity: 0.6; cursor: default; }
  .file-icon { flex-shrink: 0; }
  .file-path { flex: 1; font-family: monospace; font-size: 0.82rem; }
  .file-size { font-size: 0.72rem; color: var(--text-muted); flex-shrink: 0; }

  /* Instructions preview */
  .instructions-section {
    background: var(--surface); border: 1px solid var(--border);
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
  .instructions-body :global(code) { background: #f0ebe5; padding: 0.1rem 0.3rem; border-radius: 3px; font-size: 0.85em; }

  /* File article (file view/edit) */
  .file-article {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 1.5rem 2rem;
  }
  .file-article header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid var(--border);
  }
  .file-article h1 {
    font-family: monospace; font-weight: 600; font-size: 1rem; margin: 0; color: var(--text);
  }
  .file-article .file-size { font-size: 0.75rem; color: var(--text-muted); }
  .file-body { font-size: 0.9rem; line-height: 1.6; }
  .file-body pre {
    background: #f5f0ea; padding: 1rem; border-radius: var(--radius);
    overflow-x: auto; font-size: 0.82rem;
  }
  .file-body :global(h1), .file-body :global(h2), .file-body :global(h3) { font-family: var(--font-serif); margin: 1rem 0 0.4rem; }
  .file-body :global(p) { margin: 0.4rem 0; }
  .file-body :global(ul), .file-body :global(ol) { margin: 0.4rem 0; padding-left: 1.5rem; }
  .file-body :global(code) { background: #f0ebe5; padding: 0.1rem 0.3rem; border-radius: 3px; font-size: 0.85em; }
  .file-body :global(a) { color: var(--terracotta); }

  /* Edit button & editor */
  .btn-edit {
    float: right; background: none; border: 1px solid var(--border);
    border-radius: var(--radius); padding: 0.3rem 0.75rem;
    font-size: 0.78rem; color: var(--text-muted); cursor: pointer;
    transition: border-color 0.15s, color 0.15s;
  }
  .btn-edit:hover { border-color: var(--terracotta); color: var(--terracotta); }
  .file-editor { display: flex; flex-direction: column; gap: 0.75rem; }
  .editor-actions { display: flex; justify-content: flex-end; gap: 0.5rem; }
  .btn {
    padding: 0.4rem 1rem; border-radius: var(--radius);
    font-size: 0.82rem; font-weight: 500; cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
  }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-secondary { background: var(--surface); border: 1px solid var(--border); color: var(--text-muted); }
  .btn-secondary:hover:not(:disabled) { border-color: var(--text-muted); }
  .btn-primary { background: var(--terracotta); border: 1px solid var(--terracotta); color: #fff; }
  .btn-primary:hover:not(:disabled) { background: #b35a36; border-color: #b35a36; }

  /* Empty & loading */
  .empty { text-align: center; padding: 3rem 1rem; color: var(--text-muted); }
  .empty p { font-family: var(--font-serif); font-style: italic; font-size: 1.1rem; margin: 0 0 0.5rem; }
  .empty small { font-size: 0.82rem; }
  .loading { display: flex; justify-content: center; gap: 0.5rem; padding: 4rem 0; }
  .loading-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--terracotta); opacity: 0.3;
    animation: pulse 1s ease-in-out infinite;
  }
  .loading-dot:nth-child(2) { animation-delay: 0.15s; }
  .loading-dot:nth-child(3) { animation-delay: 0.3s; }
  @keyframes pulse {
    0%, 100% { opacity: 0.3; transform: scale(1); }
    50% { opacity: 1; transform: scale(1.2); }
  }
  .error-card {
    background: #fef2f0; border: 1px solid #f0c4bc;
    border-radius: var(--radius); padding: 1.5rem; text-align: center; color: var(--terracotta);
  }
  .error-card p { margin: 0 0 0.5rem; font-weight: 500; }
  .error-card small { color: var(--text-muted); }

  @media (max-width: 640px) {
    .file-article { padding: 1rem 1.25rem; }
  }
</style>

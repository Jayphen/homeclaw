import { readFileSync } from 'node:fs';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

function getVersion() {
  // Use env var (set by CI) or extract from pyproject.toml
  if (process.env.HOMECLAW_VERSION) return process.env.HOMECLAW_VERSION;
  try {
    const pyproject = readFileSync('../pyproject.toml', 'utf-8');
    const match = pyproject.match(/^version\s*=\s*"(.+)"/m);
    return match ? match[1] : 'dev';
  } catch {
    return 'dev';
  }
}

export default defineConfig({
  plugins: [sveltekit()],
  define: {
    __HOMECLAW_VERSION__: JSON.stringify(getVersion())
  }
});

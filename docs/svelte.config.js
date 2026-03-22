import adapter from '@sveltejs/adapter-static';
import { mdsvex } from 'mdsvex';
import { createHighlighter } from 'shiki';

const highlighter = await createHighlighter({
  themes: ['github-dark'],
  langs: ['bash', 'python', 'javascript', 'typescript', 'svelte', 'json', 'yaml', 'markdown', 'docker', 'html', 'css']
});

/** @type {import('@sveltejs/kit').Config} */
const config = {
  extensions: ['.svelte', '.md'],

  preprocess: [
    mdsvex({
      extensions: ['.md'],
      highlight: {
        highlighter: (code, lang) => {
          const html = highlighter.codeToHtml(code, { lang: lang || 'text', theme: 'github-dark' });
          return `{@html \`${html.replace(/`/g, '\\`')}\`}`;
        }
      }
    })
  ],

  kit: {
    adapter: adapter({
      pages: 'build',
      assets: 'build',
      fallback: '404.html',
      precompress: true,
      strict: true
    }),
    paths: {
      base: ''
    }
  }
};

export default config;

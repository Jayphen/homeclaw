import { marked } from "marked";
import DOMPurify from "dompurify";

marked.setOptions({ breaks: true, gfm: true });

/** Render markdown to sanitized HTML. */
export function renderMarkdown(src: string): string {
  return DOMPurify.sanitize(marked.parse(src) as string);
}

/**
 * Render markdown in a compact preview context — full block rendering
 * (headings, lists, etc.) but intended to be styled compactly via CSS.
 */
export function renderPreviewMarkdown(src: string): string {
  return DOMPurify.sanitize(marked.parse(src) as string);
}

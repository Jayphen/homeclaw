import { marked } from "marked";
import DOMPurify from "dompurify";

marked.setOptions({ breaks: true, gfm: true });

/** Render markdown to sanitized HTML. */
export function renderMarkdown(src: string): string {
  return DOMPurify.sanitize(marked.parse(src) as string);
}

/**
 * Render a short markdown preview — inline only (no block elements).
 * Strips headings markers, renders bold/italic/code, returns a single
 * line of HTML suitable for use inside a <p> or <span>.
 */
export function renderInlineMarkdown(src: string): string {
  return DOMPurify.sanitize(marked.parseInline(src) as string);
}

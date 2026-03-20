import { marked } from "marked";
import DOMPurify from "dompurify";

marked.setOptions({ breaks: true, gfm: true });

/** Render markdown to sanitized HTML. */
export function renderMarkdown(src: string): string {
  return DOMPurify.sanitize(marked.parse(src) as string);
}

/**
 * Render a short markdown preview — strips block-level syntax (headings,
 * list markers, blockquotes) then renders inline formatting (bold, italic,
 * code, links). Returns a single line of HTML for use inside a <p>.
 */
export function renderInlineMarkdown(src: string): string {
  const stripped = src
    .replace(/^#{1,6}\s+/gm, "")       // ## Heading → Heading
    .replace(/^[-*+]\s+/gm, "")         // - item → item
    .replace(/^\d+\.\s+/gm, "")         // 1. item → item
    .replace(/^>\s?/gm, "")             // > quote → quote
    .replace(/\n/g, " ")                // collapse to single line
    .replace(/\s{2,}/g, " ")            // collapse whitespace
    .trim();
  return DOMPurify.sanitize(marked.parseInline(stripped) as string);
}

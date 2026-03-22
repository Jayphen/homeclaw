# Design System: The Digital Conservatory

## 1. Overview & Creative North Star

This design system is built upon the Creative North Star of **"The Digital Conservatory."** Much like a sun-drenched home office filled with plants and leather-bound journals, the interface must feel breathable, curated, and intentionally quiet.

We are moving away from the rigid, "boxed-in" aesthetic of traditional SaaS dashboards. Instead, we embrace a high-end editorial feel that uses **intentional asymmetry** and **tonal depth** to guide the user’s eye. The goal is to make the management of household AI feel less like "task management" and more like "stewardship." We achieve this through generous white space, a sophisticated serif/sans-serif interplay, and a tactile physics that makes digital elements feel like physical objects resting on a desk.

---

## 2. Colors & Surface Philosophy

The palette is rooted in organic, earth-toned neutrals designed to reduce cognitive load and eye strain.

### The "No-Line" Rule

To achieve a premium, custom feel, **prohibit the use of 1px solid borders for sectioning or dividing content.** Traditional dividers create visual noise. Instead, boundaries must be defined through:

1. **Background Color Shifts:** Placing a `surface_container_low` section against a `surface` background.
2. **Tonal Transitions:** Using whitespace and grouping rather than physical lines.

### Surface Hierarchy & Nesting

Treat the UI as a physical stack of fine paper. We use Material-based tokens to define importance:

* **Base Layer:** `surface` (#fcf9f1) — The desk surface.
* **Lowered Sections:** `surface_container_low` (#f6f3eb) — Use this for sidebar backgrounds or secondary content wells.
* **Elevated Components:** `surface_container_lowest` (#ffffff) — Use this for the primary cards (Agents, Actions) to create a subtle "pop" against the cream background.

### The "Glass & Gradient" Rule

Flat colors can feel clinical. To add "soul":

* **Signature Gradients:** For primary CTAs or high-impact cards, use a subtle linear gradient transitioning from `primary` (#56642b) to `primary_container` (#8a9a5b).
* **Glassmorphism:** For floating navigation bars or modal overlays, use a semi-transparent `surface_bright` with a `20px` backdrop-blur. This ensures the "warmth" of the background bleeds through the UI.

---

## 3. Typography: The Editorial Voice

Our typography hierarchy is designed to feel like a high-end lifestyle magazine—authoritative yet warm.

* **The Display & Headline (Newsreader):** Use the serif for all high-level messaging. It provides a sense of history and trust. For `display-lg`, use a tight letter-spacing (-0.02em) to give it a modern, custom-type feel.
* **The UI & Label (Plus Jakarta Sans):** A friendly, geometric sans-serif for functional elements. Its high x-height ensures readability even at `label-sm` sizes.
* **The Interplay:** Always pair a `headline-sm` (Serif) with a `label-md` (Sans, All Caps, 0.05em tracking) to create a sophisticated, tiered information hierarchy.

---

## 4. Elevation & Depth

In this design system, depth is a feeling, not a shadow.

### The Layering Principle

Achieve hierarchy by stacking surface tiers. A `surface_container_lowest` card placed on a `surface_container_low` background creates a natural, soft lift. Avoid stacking more than three layers deep to maintain the "Home Office" simplicity.

### Ambient Shadows

Shadows should be rare and used only for "active" floating elements (e.g., a dragged card or a triggered dropdown).

* **Specs:** `Blur: 40px`, `Spread: -10px`, `Opacity: 6%`.
* **Tinting:** Never use pure black. The shadow color must be a tinted version of `on_surface` (#1c1c17) to mimic natural ambient light.

### The "Ghost Border" Fallback

If a border is required for accessibility (e.g., input fields or high-contrast card states), use a **Ghost Border**.

* **Token:** `outline_variant` (#c6c8b8) at **20% opacity**.
* **Rule:** Never use 100% opaque borders; they shatter the "softness" of the Conservatory aesthetic.

---

## 5. Components

### Buttons

* **Primary:** Solid `primary` (Sage) with `on_primary` text. Use `rounded-xl` (3rem) for a pill-shaped, approachable feel.
* **Secondary:** `secondary` (Terracotta) for "Action" items (like "Settings" or "Run Agent").
* **Tertiary:** Transparent background with `primary` text. Use for low-emphasis navigation.

### Cards (The "Agent" Card)

* **Styling:** Background `surface_container_lowest`, corner radius `lg` (2rem).
* **Layout:** No dividers. Separate the header ("Chef") from the body ("Active") using `spacing-4`.
* **Interaction:** On hover, shift the background to `surface_bright` and apply a `Ghost Border`.

### Input Fields

* **Base:** `surface_container_low` with a `Ghost Border`.
* **Roundness:** `md` (1.5rem).
* **States:** On focus, the border transitions to a 1px solid `primary` (Sage) to provide clear, tactile feedback.

### Lists & Activity Logs

* **Forbid Dividers:** Do not use lines between list items.
* **Grouping:** Use `spacing-2` between items. Use a subtle background shift (alternating `surface` and `surface_container_low`) for long logs to maintain readability without the "grid" look.

---

## 6. Do’s and Don’ts

### Do

* **Embrace Asymmetry:** Align headings to the left while floating action buttons to the right with generous, uneven margins.
* **Use Tactile Spacing:** Use `spacing-8` (2.75rem) or `spacing-10` (3.5rem) between major sections to let the design "breathe."
* **Nesting:** Place white cards on cream backgrounds. The subtle contrast is the height of luxury.

### Don’t

* **Don't use pure black:** Use `on_surface` (#1c1c17) for all text to keep the "charcoal" softness.
* **Don't use Sharp Corners:** Nothing in the Conservatory is sharp. Every element must have a minimum radius of `sm` (0.5rem), with most containers using `lg` (2rem) or `xl` (3rem).
* **Don't Over-Shadow:** If the layout feels flat, change the background color of the container instead of adding a shadow. Tonal layering is always the preference.

### Accessibility Note

While we use soft tones, always ensure text-to-background contrast meets WCAG AA standards. Use the `on_primary` and `on_secondary` tokens specifically designed to provide high legibility against our Sage and Terracotta accents.

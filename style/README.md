# boost style — *Aurora living-glass*

The visual identity of boost, packaged as a small, dependency-free design
system you can drop into any static page.

It's a **neon-tech, glassmorphic** look: a **cyan → violet → pink** triad on a
near-black ground, an ambient **aurora** that drifts slowly behind the page, and
**glass cards that light up under the cursor**. The goal is a page that feels
*slightly alive but not distracting* — every motion is slow, low-contrast, and
gated behind `prefers-reduced-motion`.

Open [`demo.html`](demo.html) to see the whole system on one page.

```text
style/
├── boost.css     the design system — tokens, atmosphere, primitives, a11y
├── boost.js      two progressive enhancements: cursor glow + reveal-on-scroll
├── demo.html     self-contained showcase / living reference
└── README.md     this file
```

## Use it

```html
<link rel="stylesheet" href="style/boost.css">
<!-- optional: cursor spotlight + reveal-on-scroll -->
<script src="style/boost.js" defer></script>
```

Everything is static — no build step, no dependencies, no webfont fetches. The
JavaScript is pure enhancement: with it disabled, the page is still fully styled
and legible (cards just don't glow, and reveal elements start visible).

## The palette

The entire identity lives in three custom properties. Recolor the system by
changing their **values** — never the selectors.

| Token       | Value     | Role                          |
|-------------|-----------|-------------------------------|
| `--cyan`    | `#22d3ee` | primary accent                |
| `--violet`  | `#a855f7` | secondary accent              |
| `--pink`    | `#f472d0` | tertiary accent               |
| `--bg`      | `#07080f` | near-black page ground        |
| `--text`    | `#e9ebf5` | primary ink                   |
| `--grad`    | cyan → violet → pink | the signature gradient |

Neutrals are intentionally cool (a slight blue bias), not pure grey, so they
read as chosen rather than defaulted.

## What's in the box

| Class            | What it gives you                                                        |
|------------------|--------------------------------------------------------------------------|
| `.wrap`          | centered `max-width` container that sits above the aurora                |
| `.glass`         | the reusable living-glass surface — blur, hover lift, cursor spotlight   |
| `.cap`           | a padded glass **card** with icon slot (`--ic-bg`/`--ic-fg`), title, tags |
| `.stat` / `.stats` | gradient stat figures in a responsive grid                             |
| `.badge`         | a "live" pill with a breathing dot                                       |
| `.btn` `.btn-grad` `.btn-ghost` | the two button treatments                                |
| `.eyebrow` `.sec-title` `.sec-sub` | section chrome (eyebrow is gradient-clipped)          |
| `.grad-text`     | gradient-clip any inline text                                            |
| `.window`        | a macOS-style terminal frame + `.tp/.tv/.tc/.tok/.cm` syntax tokens      |
| `.reveal`        | fades/slides in when scrolled into view (via `boost.js`)                 |

### The atmosphere

`body::before` (drifting aurora) and `body::after` (masked tech grid) are fixed
layers at `z-index: 0`. Keep your content inside `.wrap` (which sets
`z-index: 1`) so it sits above them.

### The cursor spotlight

`boost.js` writes the pointer's element-local position into `--mx` / `--my` on
each `.glass`, `.cap`, `.stat`, and `.window`. The CSS reads those in a radial
gradient. No JS → the variables stay unset → the spotlight simply never shows,
and the hover lift still works.

## Accessibility

- **`prefers-reduced-motion`** disables the aurora drift, the breathing badge,
  the reveal animation, and the hover lift — hover still recolors, just without
  movement.
- **Print** hides the atmosphere and flattens shadows/blur so pages print clean.
- **Focus** states are visible (`:focus-visible` uses the cyan accent).
- Contrast targets legible body text (`--text` on `--bg`) at the default sizes.

## Provenance

This is the aesthetic used across the boost documentation and
[jonnyeclectic's portfolio](https://github.com/jonnyeclectic/portfolio),
extracted here as a standalone, reusable system.

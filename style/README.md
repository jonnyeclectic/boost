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
| `--cyan`    | `#40cbe3` | primary accent                |
| `--violet`  | `#cc9eff` | secondary accent              |
| `--pink`    | `#f58fd7` | tertiary accent               |
| `--bg`      | `#07080f` | near-black page ground        |
| `--text`    | `#d6d9e3` | primary ink                   |
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

## Type

Both stacks are system fonts, so the system fetches nothing and there is no
flash on load.

A page may justify one display face. Three things then bite, and all three fail
silently — the page renders, it just renders wrong.

| Trap | What happens | The fix |
|------|--------------|---------|
| Enumerated weights | `wght@400;500;600` loads those three. `font-weight: 700` is then *synthesised*: the browser smears the 600 outline. | Request the axis: `wght@400..900`. |
| Missing italic axis | `font-style: italic` shears the roman instead of loading the italic. On a high-contrast face a true italic is a different alphabet, so the fake reads immediately. | `ital,wght@0,400..900;1,400..900`, plus `font-synthesis: none` so the fallback is visible rather than silent. |
| Display weight on a dark ground | A high-contrast face at 500 has hairline strokes. On `--bg` they dissolve, and under `background-clip: text` they take the gradient with them. | Set display type at 700+. Specimen sheets flatter 400-500 on white; this ground is not white. |

To check a face actually loaded rather than trusting the render, compare advance
widths in the console — a real italic sets narrower than a sheared roman:

```js
const w = (style, weight) => {
  const c = document.createElement('canvas').getContext('2d');
  c.font = `${style} ${weight} 100px "Your Face"`;
  return c.measureText('remembered').width;
};
w('normal', 700);   // 612.4
w('italic', 800);   // 576.7  <- a real italic cut, not a slant
```

### Gradient on type

`.grad-text` paints only where a glyph is, so weight is a contrast control here
rather than a style choice. Thin strokes give the ramp no area, and the text
fades toward whichever stop sits closest to the ground. Anything wearing it
wants 600+; `.eyebrow` (700) and `.stat b` (800) are the reference.

## Writing

Prose is part of the system. `.vale/styles/boost/AIWriting.yml` enforces the
mechanical half of this and runs in the `prose-lint` workflow over every
contributor-facing Markdown file, including this one. All 13 scored zero hits
before the rule landed, so it gates new drafts rather than grandfathering old
ones.

Vale reads tokens, so it catches vocabulary and nothing else. These three are
properties of a whole passage and need a human:

**Em-dash density.** One is punctuation. Nine on a screen is a signature. The
rule is not abstinence — this repo's own docs use them well — it is noticing
when every other sentence has grown a subordinate clause instead of a full
stop. A draft that arrives at ~25 per page is not written, it is generated.

**Rule of three.** Three-item lists and three-clause sentences are the default
cadence of generated prose. One is fine. Three sections in a row that each
open with three parallel clauses is a tell.

**Significance closers.** A sentence whose job is to assert that the preceding
sentence mattered. `This is the part that really matters`, `that is the whole
point`, `it is worth noting that`. Cut them and nothing is lost, which is the
diagnostic: they carry no information the reader did not already have.

Two habits that replace all three: say what a thing does rather than what it
represents, and prefer the shorter of two accurate sentences.

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

// Visual-regression sweep for the docs pages: load each page in headless
// Chrome at the responsive breakpoints and assert the invariants that a CSS
// slip actually breaks — no horizontal overflow, the Aurora chrome present,
// key sections rendered, stylesheet actually applied. Screenshots land in
// tests/visual/out/ for eyeballing; the exit code is the gate.
//
//   node tests/visual/visual_check.mjs             # system Chrome
//   BOOST_CHROME_BIN=/path/to/chrome node ...      # explicit binary
//
// Runs against the LOCAL working tree (file://), so a PR's CSS/HTML changes
// are what gets checked — no deploy needed.
//
// Pages: all nine, generated ones included. The list used to hold only the four
// hand-authored surfaces, on the reasoning that "the generated boards are
// covered by their build --check instead". They are not: `--check` proves the
// HTML still matches the generator, which stays true when the bug IS the
// generator. commands.html shipped `grid-template-columns: … 1fr` for months —
// a track that will not shrink below its widest unbreakable flag name — and
// scrolled sideways 241px at 320px wide, 171px at 390px, 61px at 768px. Every
// width was already in WIDTHS below; only the page was missing.
import { launch } from "puppeteer-core";
import { mkdirSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const OUT = resolve(root, "tests/visual/out");
mkdirSync(OUT, { recursive: true });

const PAGES = [
  "docs/index.html", "docs/adapters.html", "docs/eval.html", "docs/mcp-hub.html",
  "docs/commands.html", "docs/demo.html", "docs/chat.html",
  "docs/roadmap.html", "docs/design-roadmap.html",
];
const WIDTHS = [375, 768, 1024, 1280, 1680];

const CANDIDATE_BINS = [
  process.env.BOOST_CHROME_BIN,
  "/usr/bin/google-chrome",                                   // CI (ubuntu)
  "/usr/bin/chromium-browser",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
].filter(Boolean);
const bin = CANDIDATE_BINS.find((p) => existsSync(p));
if (!bin) {
  console.error("visual-check: no Chrome binary found (set BOOST_CHROME_BIN)");
  process.exit(2);
}

const browser = await launch({
  executablePath: bin,
  pipe: true,                       // no listening socket (sandbox-safe)
  headless: "shell",
  args: ["--no-sandbox", "--disable-gpu", "--in-process-gpu", "--single-process",
         "--disable-dev-shm-usage", "--hide-scrollbars"],
});

// Containers allowed to hide content behind their own horizontal scroll.
//
// The document-level assertion below is blind to these by construction: an
// element with `overflow-x: auto` ABSORBS its overflow, so
// `documentElement.scrollWidth` stays equal to the viewport no matter how much
// is hidden inside. That is how the registries table shipped 812px of content
// into a 340px scroller — 21 of its 24 cells off-screen — past a gate that
// reported "9 pages × 5 widths clean". macOS and iOS overlay scrollbars paint
// nothing until a scroll is already under way, so it did not look truncated
// either.
//
// An allowlist rather than a threshold, because "how much may be hidden" is not
// the question — whether the reader can tell is. Each entry needs a reason, and
// anything new fails until someone writes one. That is the ratchet: the cost of
// adding a scroller is one sentence, and the cost of adding one by accident is
// a red build.
const SCROLL_OK = [
  { sel: "header .nav ul, .site-nav ul",
    why: "mobile nav strip — snap points and a faded trailing edge already read as scrollable" },
  { sel: "pre",
    why: "code must not wrap; a broken command line is worse than a hidden one" },
  { sel: ".diagram",
    why: "fixed-geometry diagram — reflowing it would move the arrows off their boxes" },
  { sel: "table.contract, table.map",
    why: "columns exist to be compared, so stacking would destroy the point; boost.css keeps a visible scrollbar on them" },
];
const SCROLL_OK_SEL = SCROLL_OK.map((s) => s.sel).join(", ");

let failures = 0;
const page = await browser.newPage();
await page.emulateMediaFeatures([{ name: "prefers-reduced-motion", value: "reduce" }]);

for (const rel of PAGES) {
  const url = "file://" + resolve(root, rel);
  for (const width of WIDTHS) {
    await page.setViewport({ width, height: 950 });
    await page.goto(url, { waitUntil: "load", timeout: 30000 });
    // reveal-on-scroll content sits at opacity 0 until it intersects; force
    // everything visible so the screenshot shows the real layout.
    await page.addStyleTag({ content: ".reveal{opacity:1!important;transform:none!important}" });

    const r = await page.evaluate((okSel) => {
      const doc = document.documentElement;
      const overflowPx = Math.max(0, doc.scrollWidth - doc.clientWidth);
      const css = getComputedStyle(document.body);

      // Per-container overflow: what the document-level number cannot see.
      const vw = window.innerWidth;
      const clipped = [];
      document.querySelectorAll("*").forEach((el) => {
        const hidden = el.scrollWidth - el.clientWidth;
        if (hidden <= 1 || el.clientWidth === 0) return;   // 1px = subpixel noise
        const cs = getComputedStyle(el);
        if (cs.overflowX !== "auto" && cs.overflowX !== "scroll") return;
        if (okSel && el.matches(okSel)) return;
        // Count what a reader actually cannot see right now. `hidden` alone
        // overstates a container scrolled to the middle and understates one
        // whose overflow is a single very wide child.
        let off = 0;
        el.querySelectorAll("*").forEach((c) => {
          const b = c.getBoundingClientRect();
          if (b.width > 0 && (b.right > vw + 0.5 || b.left < -0.5)) off++;
        });
        clipped.push({
          sel: el.tagName.toLowerCase() + (el.id ? "#" + el.id : "") +
            (typeof el.className === "string" && el.className.trim()
              ? "." + el.className.trim().split(/\s+/).join(".") : ""),
          hidden, off,
        });
      });

      return {
        overflowPx,
        clipped,
        bg: css.backgroundColor,
        fontOk: css.fontFamily.length > 0,
        // index has a <header> nav; adapters/eval/mcp-hub use breadcrumb
        // heroes — the shared invariant is the .wrap content column.
        hasWrap: !!document.querySelector(".wrap"),
        headings: document.querySelectorAll("h1,h2").length,
      };
    }, SCROLL_OK_SEL);

    const name = rel.replace(/[\/.]/g, "_") + "-" + width;
    const problems = [];
    if (r.overflowPx > 0) problems.push(`horizontal overflow ${r.overflowPx}px`);
    for (const c of r.clipped) {
      problems.push(`${c.sel} hides ${c.hidden}px behind its own scroll `
        + `(${c.off} element(s) off-screen) — fix it, or add it to SCROLL_OK with a reason`);
    }
    // boost.css paints the near-black ground; white/transparent means the
    // stylesheet did not load or a cascade break unstyled the page.
    if (!/rgb\(7, 8, 15\)/.test(r.bg)) problems.push(`body background ${r.bg} (stylesheet not applied?)`);
    if (!r.hasWrap) problems.push("chrome missing (.wrap)");
    if (r.headings < 2) problems.push(`only ${r.headings} headings rendered`);

    await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: width === 1280 });
    if (problems.length) {
      failures++;
      console.error(`FAIL ${rel} @${width}: ${problems.join("; ")}`);
    } else {
      console.log(`PASS ${rel} @${width}`);
    }
  }
}

await browser.close();
if (failures) {
  console.error(`visual-check: ${failures} failing page/width combinations`);
  process.exit(1);
}
console.log(`visual-check: OK — ${PAGES.length} pages × ${WIDTHS.length} widths clean`);

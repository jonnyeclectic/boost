// axe-core sweep for the docs pages — the WCAG checks that need a live DOM.
//
//   node tests/visual/a11y_check.mjs                # system Chrome
//   BOOST_CHROME_BIN=/path/to/chrome node ...       # explicit binary
//
// On macOS, point BOOST_CHROME_BIN at a `chrome-headless-shell` rather than at
// Google Chrome: Chrome's ProcessSingleton bind()s a unix socket and aborts "to
// avoid profile corruption" wherever that syscall is denied, and no flag turns
// it off. The shell binary has no ProcessSingleton.
//
// scripts/a11y_check.py is the always-on gate: it covers everything decidable
// from the markup (lang, alt, accessible names, duplicate ids, heading order)
// plus the 1.4.3 contrast ratios computed from the Aurora tokens, with no
// browser at all. This is the other half — the rules that only exist once the
// page is laid out and the accessibility tree is computed:
//
//   * color-contrast as RENDERED, including text over the glass panels and the
//     gradient, which no token-pair table can predict;
//   * ARIA attribute/role validity against the computed tree;
//   * landmark and region structure;
//   * elements hidden from assistive tech but still focusable.
//
// Runs against the LOCAL working tree (file://) like visual_check.mjs, so a PR's
// own HTML/CSS is what gets audited — no deploy needed.
import { launch } from "puppeteer-core";
import { readFileSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

// Every page, not just the hand-authored four: the generated boards carry the
// same chrome and are where a heading-order or landmark slip actually shipped.
const PAGES = [
  "docs/index.html", "docs/adapters.html", "docs/eval.html", "docs/mcp-hub.html",
  "docs/roadmap.html", "docs/design-roadmap.html", "docs/commands.html",
  "docs/demo.html", "docs/chat.html", "docs/langchain.html",
];

// WCAG 2.1 A + AA. Deliberately not "best-practice": those are opinions, and a
// gate that fails on an opinion is a gate people learn to route around.
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

const axePath = resolve(root, "tests/visual/node_modules/axe-core/axe.min.js");
if (!existsSync(axePath)) {
  console.error("a11y-check: axe-core not installed (npm install in tests/visual)");
  process.exit(2);
}
const axeSource = readFileSync(axePath, "utf8");

const CANDIDATE_BINS = [
  process.env.BOOST_CHROME_BIN,
  "/usr/bin/google-chrome",                                   // CI (ubuntu)
  "/usr/bin/chromium-browser",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
].filter(Boolean);
const bin = CANDIDATE_BINS.find((p) => existsSync(p));
if (!bin) {
  console.error("a11y-check: no Chrome binary found (set BOOST_CHROME_BIN)");
  process.exit(2);
}

// chrome-headless-shell is the only binary that starts under a macOS sandbox
// that denies Mach port rendezvous — and it needs --single-process to do it, or
// it dies in bootstrap_check_in before the CDP pipe is ever ready and puppeteer
// reports a bare ProtocolError from launch(). visual_check.mjs already passes
// the flag, which is why that half of this directory ran locally and this half
// did not. Scoped to the shell binary on purpose rather than passed
// unconditionally: CI drives /usr/bin/google-chrome in NEW headless (this
// script takes puppeteer's default; visual_check.mjs asks for "shell"), and
// --single-process is a debug-only flag there whose interaction with new
// headless nothing in this repo exercises. Conditioning on the binary keeps
// the CI invocation byte-identical while making the local run work.
const needsSingleProcess = /chrome[-_]headless[-_]shell/.test(bin);

const browser = await launch({
  executablePath: bin,
  pipe: true,                       // no listening socket (sandbox-safe)
  // file:// pages load ../style/boost.css as a subresource; without this Chrome
  // treats each file as its own opaque origin and the stylesheet never applies,
  // which would make every contrast result meaningless.
  args: [
    "--allow-file-access-from-files", "--no-sandbox",
    ...(needsSingleProcess ? ["--single-process"] : []),
  ],
});

// ---------------------------------------------------------------------------
// Gradient contrast — the half axe cannot do.
//
// axe composites a solid background and gives up on anything else: text over a
// `linear-gradient` comes back as `incomplete`, never as a `violation`. This
// script fails on `result.violations` alone, so those nodes counted as passing
// — 153 of them across the docs, including `.cta`, `.grad`, `.btn-grad` and the
// hero stat numbers, which is to say every signature element of the Aurora
// system. The header CTA shipped at 1.37:1 (needs 4.5) and both gates were
// green; scripts/a11y_check.py missed it too, because it grades solid token
// pairs and a gradient is not one.
//
// A gradient has no single background colour, so grade against EVERY stop and
// keep the worst: text that passes over the light end of a gradient and fails
// over the dark end fails, because a reader gets whichever end their glyph
// happens to sit on.
//
// Two shapes, and they invert:
//   * text over a gradient panel  — grade the text colour against each stop;
//   * `background-clip: text`     — the gradient IS the text, so grade each
//                                   stop against whatever is painted behind it.
// Getting that backwards passes gradient text by comparing it to itself.
const GRADIENT_CONTRAST = () => {
  const parse = (s) => {
    const m = String(s).match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[,\s/]+/).filter(Boolean).map(Number);
    if (p.length < 3 || p.some(Number.isNaN)) return null;
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  };
  const lum = (c) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  const ratio = (a, b) => {
    const [x, y] = [lum(a), lum(b)];
    return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
  };
  const over = (fg, bg) => ({
    r: fg.r * fg.a + bg.r * (1 - fg.a),
    g: fg.g * fg.a + bg.g * (1 - fg.a),
    b: fg.b * fg.a + bg.b * (1 - fg.a), a: 1,
  });
  // The solid colour actually painted behind an element: the Aurora panels are
  // translucent, so the nearest ancestor with a background is rarely opaque and
  // taking it at face value would grade against a colour nobody sees.
  const CANVAS = { r: 7, g: 8, b: 15, a: 1 };          // --bg, the page ground
  const behind = (el) => {
    let acc = null;
    for (let n = el; n; n = n.parentElement) {
      const c = parse(getComputedStyle(n).backgroundColor);
      if (!c || c.a === 0) continue;
      acc = acc ? over(acc, c) : c;
      if (c.a === 1) break;
    }
    if (!acc) return CANVAS;
    return acc.a < 1 ? over(acc, CANVAS) : acc;
  };
  // Only elements holding their own text: a wrapper's colour says nothing about
  // a child that sets its own, and counting it double-reports every nesting.
  const hasOwnText = (el) =>
    [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length);

  const out = [];
  document.querySelectorAll("*").forEach((el) => {
    const cs = getComputedStyle(el);
    if (!/gradient/.test(cs.backgroundImage || "")) return;
    if (cs.visibility === "hidden" || cs.display === "none") return;
    const box = el.getBoundingClientRect();
    if (box.width < 1 || box.height < 1) return;
    if (!hasOwnText(el)) return;
    // Fully transparent stops are spacers in a fade, not colours a glyph sits on.
    const stops = (cs.backgroundImage.match(/rgba?\([^)]*\)/g) || [])
      .map(parse).filter((c) => c && c.a > 0.05);
    if (!stops.length) return;

    const px = parseFloat(cs.fontSize) || 16;
    const bold = (parseInt(cs.fontWeight, 10) || 400) >= 700;
    const large = px >= 24 || (px >= 18.66 && bold);   // WCAG 1.4.3 "large text"
    const need = large ? 3.0 : 4.5;
    const sel = el.tagName.toLowerCase() +
      (typeof el.className === "string" && el.className.trim()
        ? "." + el.className.trim().split(/\s+/).join(".") : "");
    const text = (el.textContent || "").trim().slice(0, 40);

    let got, kind;
    if ((cs.webkitBackgroundClip || cs.backgroundClip) === "text") {
      const bg = behind(el.parentElement || el);
      got = Math.min(...stops.map((s) => ratio(over(s, bg), bg)));
      kind = "gradient-text";
    } else {
      const fg = parse(cs.color);
      if (!fg) return;
      got = Math.min(...stops.map((s) => {
        const bg = over(s, behind(el));
        return ratio(over(fg, bg), bg);
      }));
      kind = "text-on-gradient";
    }
    out.push({ kind, sel, text, need, got: Math.round(got * 100) / 100 });
  });
  return out;
};

let violatingNodes = 0;
let gradientsChecked = 0;
for (const rel of PAGES) {
  const file = resolve(root, rel);
  if (!existsSync(file)) {
    console.error(`a11y-check: ${rel} is missing`);
    violatingNodes++;
    continue;
  }
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });
  // Emulate prefers-reduced-motion BEFORE navigating. `.js .reveal` fades in
  // over 600ms (opacity 0 -> 1), and axe computes contrast from the COMPOSITED
  // colour — so running mid-transition reports --text-3 (#767c96, a genuine
  // 4.85:1) as whatever partial-opacity blend it caught: #363948, #505467 and
  // #656a81 were all observed, at 20%, 44% and 72% of the token's luminance.
  // None of those exist anywhere in the repo, which is what made the failures
  // look like a phantom.
  //
  // boost.css already handles this: its `prefers-reduced-motion: reduce` block
  // forces `opacity: 1 !important` on .reveal. The sweep simply never asked for
  // it. Emulating the feature is also more honest than waiting out the
  // animation — it audits the page as a motion-sensitive user receives it.
  await page.emulateMediaFeatures([
    { name: "prefers-reduced-motion", value: "reduce" },
  ]);
  await page.goto("file://" + file, { waitUntil: "load" });

  // Guard: prove the page is actually styled before trusting a contrast result.
  // Most pages link ../style/boost.css RELATIVELY over file://, which only
  // works because of --allow-file-access-from-files, and that flag has
  // intermittently not taken effect on the runner. Colours then fall back to
  // browser defaults and axe reports a dozen confident, specific, entirely
  // fictional violations against values that appear nowhere in this repo
  // (#505467, #656a81 — the real --text-3 is #767c96 at 4.85:1, comfortably AA).
  //
  // Probe --bg, NOT --text-3: docs/commands.html is generated self-contained
  // with its tokens inline and defines no --text-3 at all, so keying on that
  // token failed a page that was perfectly styled. --bg is defined by both the
  // shared sheet and every inline :root block, so it detects an unstyled page
  // without assuming where the styling came from.
  //
  // Failing here is the whole point: "not styled" is one line a maintainer can
  // act on, where the alternative sends them auditing a colour that has been
  // correct for months.
  const styled = await page.evaluate(() =>
    getComputedStyle(document.documentElement)
      .getPropertyValue("--bg").trim());
  if (!styled) {
    console.error(`FAIL ${rel} — page is unstyled (--bg unresolved); `
      + `every contrast result here would be meaningless, so it is reported `
      + `as a load failure rather than as violations`);
    violatingNodes++;
    await page.close();
    continue;
  }

  await page.evaluate(axeSource);
  const result = await page.evaluate(
    async (tags) => await window.axe.run(document, { runOnly: { type: "tag", values: tags } }),
    TAGS,
  );

  const gradients = await page.evaluate(GRADIENT_CONTRAST);
  gradientsChecked += gradients.length;
  const dim = gradients.filter((g) => g.got < g.need);
  if (dim.length) {
    console.error(`FAIL ${rel} — ${dim.length} gradient element(s) below AA `
      + `(axe reports these as "incomplete", never as violations)`);
    for (const g of dim) {
      console.error(`      ${g.got}:1 (needs ${g.need}) ${g.kind} ${g.sel} — "${g.text}"`);
    }
  }
  violatingNodes += dim.length;

  const violations = result.violations;
  const count = violations.reduce((n, v) => n + v.nodes.length, 0);
  violatingNodes += count;
  if (count) {
    console.error(`FAIL ${rel} — ${count} violating node(s)`);
    for (const v of violations) {
      console.error(`  [${v.impact}] ${v.id}: ${v.help}`);
      for (const node of v.nodes.slice(0, 3)) {
        console.error(`      ${node.target.join(" ")}`);
        // failureSummary is axe's own "to fix this" text — the single most
        // useful line for whoever has to act on the failure.
        if (node.failureSummary) {
          console.error(`      ${node.failureSummary.replace(/\n\s*/g, " ")}`);
        }
      }
      if (v.nodes.length > 3) console.error(`      … and ${v.nodes.length - 3} more`);
    }
  } else if (!dim.length) {
    console.log(`PASS ${rel} — ${result.passes.length} rules passed`
      + `, ${gradients.length} gradient element(s) graded`);
  }
  await page.close();
}

await browser.close();
if (violatingNodes) {
  console.error(`a11y-check: ${violatingNodes} violating node(s) across ${PAGES.length} pages`);
  process.exit(1);
}
console.log(`a11y-check: OK — ${PAGES.length} pages clean against ${TAGS.join(", ")}`
  + `, plus ${gradientsChecked} gradient element(s) graded per colour stop`);

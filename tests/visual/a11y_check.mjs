// axe-core sweep for the docs pages — the WCAG checks that need a live DOM.
//
//   node tests/visual/a11y_check.mjs                # system Chrome
//   BOOST_CHROME_BIN=/path/to/chrome node ...       # explicit binary
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
  "docs/demo.html", "docs/chat.html",
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

const browser = await launch({
  executablePath: bin,
  pipe: true,                       // no listening socket (sandbox-safe)
  // file:// pages load ../style/boost.css as a subresource; without this Chrome
  // treats each file as its own opaque origin and the stylesheet never applies,
  // which would make every contrast result meaningless.
  args: ["--allow-file-access-from-files", "--no-sandbox"],
});

let violatingNodes = 0;
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
  } else {
    console.log(`PASS ${rel} — ${result.passes.length} rules passed`);
  }
  await page.close();
}

await browser.close();
if (violatingNodes) {
  console.error(`a11y-check: ${violatingNodes} violating node(s) across ${PAGES.length} pages`);
  process.exit(1);
}
console.log(`a11y-check: OK — ${PAGES.length} pages clean against ${TAGS.join(", ")}`);

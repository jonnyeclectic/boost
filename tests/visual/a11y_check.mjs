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
  await page.goto("file://" + file, { waitUntil: "load" });
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

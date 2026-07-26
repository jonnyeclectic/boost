// Console + network health for the DEPLOYED docs site.
//
//   BOOST_SITE=https://jonnyeclectic.github.io/boost/ node tests/visual/console_check.mjs
//   node tests/visual/console_check.mjs            # defaults to the published site
//
// scripts/post_deploy_smoke.py already proves every page answers 200 and every
// local asset and link resolves — over plain HTTP, no browser needed. This is
// the part that only a real browser can see:
//
//   * uncaught JS errors and unhandled promise rejections;
//   * console.error output (boost.js degrades gracefully by design, so anything
//     it actually logs as an error is a regression);
//   * requests the page issues at RUNTIME that fail — a font, a lazily-fetched
//     asset, an XHR — which no static HTML scan can discover.
//
// Runs against the live URL, not file://, because deployment is where the paths
// change: that is the whole point of a post-deploy check.
import { launch } from "puppeteer-core";
import { existsSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const BASE = (process.env.BOOST_SITE || "https://jonnyeclectic.github.io/boost/")
  .replace(/\/?$/, "/");

// Derived from docs/, never hardcoded — scripts/check_anchors.py and
// scripts/a11y_check.py both glob docs/*.html for the same reason. A literal
// list silently stops covering a page the moment someone adds one, and the
// gap looks identical to a green run: carousel.html was live and unchecked.
const DOCS = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "docs");
const PAGES = [
  "",                                   // the site root's redirect stub
  ...readdirSync(DOCS).filter((f) => f.endsWith(".html")).sort()
    .map((f) => `docs/${f}`),
];

const CANDIDATE_BINS = [
  process.env.BOOST_CHROME_BIN,
  "/usr/bin/google-chrome",
  "/usr/bin/chromium-browser",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
].filter(Boolean);
const bin = CANDIDATE_BINS.find((p) => existsSync(p));
if (!bin) {
  console.error("console-check: no Chrome binary found (set BOOST_CHROME_BIN)");
  process.exit(2);
}

const browser = await launch({ executablePath: bin, pipe: true, args: ["--no-sandbox"] });

let failures = 0;
for (const rel of PAGES) {
  const url = BASE + rel;
  const page = await browser.newPage();
  const problems = [];

  page.on("console", (m) => {
    if (m.type() === "error") problems.push(`console.error: ${m.text().slice(0, 160)}`);
  });
  page.on("pageerror", (e) => problems.push(`uncaught: ${String(e).slice(0, 160)}`));
  page.on("requestfailed", (req) => {
    // Only same-site failures are boost's problem; a third party going down
    // must never redden a deploy check.
    if (req.url().startsWith(BASE)) {
      problems.push(`request failed: ${req.url()} (${req.failure()?.errorText})`);
    }
  });
  page.on("response", (res) => {
    if (res.status() >= 400 && res.url().startsWith(BASE)) {
      problems.push(`HTTP ${res.status()}: ${res.url()}`);
    }
  });

  try {
    // networkidle2: wait for the runtime fetches to settle, or a lazily-loaded
    // asset 404 lands after the check and goes unnoticed.
    await page.goto(url, { waitUntil: "networkidle2", timeout: 45000 });
  } catch (e) {
    problems.push(`navigation failed: ${String(e).slice(0, 160)}`);
  }

  if (problems.length) {
    failures++;
    console.error(`FAIL ${url}`);
    for (const p of problems.slice(0, 8)) console.error(`      ${p}`);
    if (problems.length > 8) console.error(`      … and ${problems.length - 8} more`);
  } else {
    console.log(`PASS ${url}`);
  }
  await page.close();
}

await browser.close();
if (failures) {
  console.error(`console-check: ${failures} of ${PAGES.length} deployed pages have errors`);
  process.exit(1);
}
console.log(`console-check: OK — ${PAGES.length} deployed pages load clean`);

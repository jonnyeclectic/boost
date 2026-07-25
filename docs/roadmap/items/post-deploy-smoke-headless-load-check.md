---
id: post-deploy-smoke-headless-load-check
board: code
section: docsite
status: inflight
category: Testing · Docs
complexity: M
impact: Med
wow: 3
note: catches red deploys
order: 9
owner: loop/post-deploy-smoke
pr:
title: Post-deploy smoke — headless load check
---
Every other docs gate runs against the working tree — <code>html-validate</code> and
           the a11y checker parse the files, the visual sweep loads them over
           <code>file://</code>. All of them can be green while the <em>deployed</em> site is
           broken, because deployment is where the paths change: Pages serves this repo
           under <code>/boost/</code>, so a link that resolves on disk can 404 in production.
           Nothing was watching that. Now, triggered by the Pages deployment finishing (so it
           checks what was actually published rather than guessing at propagation),
           <code>scripts/post_deploy_smoke.py</code> asserts every page answers 200 and every
           local asset and internal link resolves — pure stdlib over HTTP, no browser — and
           <code>console_check.mjs</code> loads each live page in headless Chrome for the
           half only a browser sees: uncaught JS, <code>console.error</code>, and runtime
           request failures. Off-site links are deliberately excluded: a flaky third party
           must never redden boost's deploy, and <code>links.yml</code> already owns those.

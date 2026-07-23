/* ============================================================================
   boost style — interactions
   ----------------------------------------------------------------------------
   Two progressive enhancements, both safe to omit:
     1. cursor-following spotlight on glass surfaces (writes --mx / --my)
     2. reveal-on-scroll for elements marked class="reveal"

   Load with `defer` (or at the end of <body>). Nothing here is required for
   the page to be styled and legible — it only adds motion.
   ========================================================================== */
(function () {
  "use strict";

  // Signal to CSS that JS is on, so .reveal can start hidden (and not trap
  // no-JS visitors with permanently-invisible content).
  document.documentElement.classList.add("js");

  const reduce = window.matchMedia &&
               window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function ready(fn) {
    if (document.readyState !== "loading") { fn(); }
    else { document.addEventListener("DOMContentLoaded", fn); }
  }

  ready(function () {
    // ---- reveal on scroll ----
    const revealables = document.querySelectorAll(".reveal");
    if (reduce || !("IntersectionObserver" in window)) {
      revealables.forEach(function (el) { el.classList.add("in"); });
    } else {
      const io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) {
            en.target.classList.add("in");
            io.unobserve(en.target);
          }
        });
      }, { rootMargin: "0px 0px -8% 0px", threshold: 0.05 });
      revealables.forEach(function (el) { io.observe(el); });
    }

    // ---- cursor-following spotlight ----
    // Pointer position is written as element-local pixels into --mx / --my,
    // which the radial-gradient in boost.css reads.
    const glassy = document.querySelectorAll(".glass, .cap, .stat, .window");
    glassy.forEach(function (el) {
      el.addEventListener("pointermove", function (e) {
        const r = el.getBoundingClientRect();
        el.style.setProperty("--mx", (e.clientX - r.left) + "px");
        el.style.setProperty("--my", (e.clientY - r.top) + "px");
      });
    });
  });
})();

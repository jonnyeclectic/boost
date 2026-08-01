/* ============================================================================
   boost style — interactions
   ----------------------------------------------------------------------------
   Two progressive enhancements, both safe to omit:
     1. reveal-on-scroll for elements marked class="reveal"

   Load with `defer` (or at the end of <body>). Nothing here is required for
   the page to be styled and legible — it only adds motion.

   The cursor-following spotlight that used to live here is gone: it was
   invisible on touch, and it ran a pointermove listener per card that wrote
   two custom properties per event, so every hover recalculated style on the
   moved element on every frame. See the Surfaces block in boost.css.
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
      return;
    }

    const io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          en.target.classList.add("in");
          io.unobserve(en.target);
        }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.05 });

    revealables.forEach(function (el) {
      // Anything already on screen at load is shown immediately rather than
      // handed to the observer. The observer does not report until after the
      // first frame, so above-the-fold content used to arrive as a visible
      // fade-in on a page the reader had not scrolled yet.
      if (el.getBoundingClientRect().top < window.innerHeight) {
        el.classList.add("in");
      } else {
        io.observe(el);
      }
    });
  });
})();

/* Global audio-language control (multilingual audio, June 2026).
 *
 * A small header control that sets a SITE-WIDE preference for which language
 * episode AUDIO plays in. It does NOT translate the page text — only the audio
 * track on episode / show pages. The preference is stored in localStorage under
 * `nn-pref-lang` (the same key the blog-post and show-page players read), and on
 * change it dispatches a `nn-langchange` CustomEvent so an on-page player can
 * switch live without a reload.
 *
 * Mirrors the safe try/catch localStorage pattern used by consent.js / search.js.
 */
(function () {
  "use strict";

  var PREF_KEY = "nn-pref-lang";
  // Short labels shown on the toggle pill per language.
  var SHORT = { en: "EN", fr: "FR", es: "ES", ru: "RU", zh: "中文" };

  function read() {
    try {
      var v = localStorage.getItem(PREF_KEY);
      return v && SHORT[v] ? v : "en";
    } catch (e) {
      return "en";
    }
  }

  function write(lang) {
    try { localStorage.setItem(PREF_KEY, lang); } catch (e) {}
  }

  function init() {
    var toggle = document.getElementById("nn-lang-toggle");
    var menu = document.getElementById("nn-lang-menu");
    var current = document.getElementById("nn-lang-current");
    if (!toggle || !menu || !current) return;

    var opts = menu.querySelectorAll(".nn-lang-opt");

    function reflect(lang) {
      current.textContent = SHORT[lang] || "EN";
      opts.forEach(function (o) {
        o.setAttribute("aria-checked", o.dataset.lang === lang ? "true" : "false");
      });
    }

    function open() {
      menu.style.display = "block";
      toggle.setAttribute("aria-expanded", "true");
    }
    function close() {
      menu.style.display = "none";
      toggle.setAttribute("aria-expanded", "false");
    }
    function isOpen() {
      return menu.style.display === "block";
    }

    reflect(read());

    toggle.addEventListener("click", function (e) {
      e.stopPropagation();
      isOpen() ? close() : open();
    });

    opts.forEach(function (o) {
      o.addEventListener("click", function () {
        var lang = o.dataset.lang;
        write(lang);
        reflect(lang);
        close();
        // Tell any on-page player (blog post / show page) to switch live.
        try {
          document.dispatchEvent(new CustomEvent("nn-langchange", { detail: { lang: lang } }));
        } catch (e) {}
      });
    });

    // Close on outside click / Escape.
    document.addEventListener("click", function (e) {
      if (isOpen() && !menu.contains(e.target) && e.target !== toggle) close();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && isOpen()) close();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

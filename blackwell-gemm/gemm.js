/* =====================================================================
   BLACKWELL GEMM · GPU switch for the profile dashboard.
   Without JavaScript both GPUs' panels show, one after the other.
   ===================================================================== */
(function () {
  "use strict";
  document.documentElement.classList.add("js");
  document.querySelectorAll("[data-gemm-dash]").forEach(function (dash) {
    var bar = dash.querySelector(".g-switch");
    var tabs = Array.prototype.slice.call(dash.querySelectorAll(".g-switch [data-gpu]"));
    var panels = Array.prototype.slice.call(dash.querySelectorAll(".g-panel[data-gpu]"));
    if (!bar || tabs.length < 2) return;
    function select(id, focus) {
      tabs.forEach(function (t) {
        var on = t.getAttribute("data-gpu") === id;
        t.setAttribute("aria-selected", on ? "true" : "false");
        t.tabIndex = on ? 0 : -1;
        if (on && focus) t.focus();
      });
      panels.forEach(function (p) { p.hidden = p.getAttribute("data-gpu") !== id; });
    }
    tabs.forEach(function (t, i) {
      t.addEventListener("click", function () { select(t.getAttribute("data-gpu"), false); });
      t.addEventListener("keydown", function (e) {
        var j = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : e.key === "Home" ? 0 : e.key === "End" ? tabs.length - 1 : null;
        if (j === null) return;
        e.preventDefault();
        select(tabs[(j + tabs.length) % tabs.length].getAttribute("data-gpu"), true);
      });
    });
    bar.hidden = false;
    select(tabs[0].getAttribute("data-gpu"), false);
  });
})();

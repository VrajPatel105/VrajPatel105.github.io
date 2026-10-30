/* =====================================================================
   VRAJ PATEL · POSTS
   Reading progress, and the bar charts. Each chart is a
   <figure class="chart" data-chart='{...}'> whose data table follows it
   as the accessible twin. Charts are drawn at 1 SVG unit = 1 CSS px and
   redrawn on resize, so axis text stays 12px at every width (a narrow
   layout replaces scaling).
   ===================================================================== */
(function () {
  "use strict";

  /* ---------- reading progress ---------- */
  const prog = document.getElementById("prog");
  if (prog) {
    let ticking = false;
    const update = () => {
      const d = document.documentElement, max = d.scrollHeight - window.innerHeight;
      prog.style.transform = "scaleX(" + (max > 0 ? Math.min(1, window.scrollY / max) : 0) + ")";
      ticking = false;
    };
    const onScroll = () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    update();
  }

  /* ---------- charts ---------- */
  const COLOR = { mine: "#b85f3e", base: "#3d6ea8", ref: "#9a978f" };
  const C = { ink: "#1b1b1b", ink2: "#5f5d58", grid: "#ebe9e3" };
  const CH = 7.3;   // approx. width of one 12px IBM Plex Mono glyph
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

  function niceStep(max, count) {
    const raw = max / count, mag = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / mag;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * mag;
  }

  function draw(fig) {
    let spec;
    try { spec = JSON.parse(fig.getAttribute("data-chart")); } catch (e) { return; }
    const plot = fig.querySelector(".chart__plot");
    if (!plot) return;
    const W = Math.floor(plot.clientWidth);
    if (W <= 0) return;
    const narrow = W < 480;
    const dec = spec.decimals || 0;
    const fmt = (v) => v.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec });
    const unit = spec.unit ? " " + spec.unit : "";
    const cats = spec.categories, series = spec.series;
    const roleOf = (s, j) => (s.roles ? s.roles[j] : s.role);

    // y scale
    let max = spec.yMax || 0;
    series.forEach((s) => s.values.forEach((v) => { if (v > max) max = v; }));
    if (spec.ref && spec.ref.value > max) max = spec.ref.value;
    const step = niceStep(max, narrow ? 4 : 5), top = Math.ceil(max / step - 1e-9) * step;
    const ticks = [];
    for (let t = 0; t <= top + 1e-9; t += step) ticks.push(t);
    const tickFmt = (t) => t.toLocaleString("en-US", { maximumFractionDigits: step < 1 ? 1 : 0 });

    const H = narrow ? 240 : 280;
    const M = { l: Math.max(...ticks.map((t) => tickFmt(t).length)) * CH + 12, r: 8, t: 24, b: 44 };
    const pw = W - M.l - M.r, ph = H - M.t - M.b;
    const y = (v) => M.t + ph - (v / top) * ph;
    const band = pw / cats.length, group = band * (narrow ? 0.8 : 0.7);
    const barW = (group - (series.length - 1) * 2) / series.length;

    // value labels only when every label fits over its bar
    let labels = !narrow;
    if (labels) series.forEach((s) => s.values.forEach((v) => { if (fmt(v).length * CH > barW + 6) labels = false; }));

    let h = '<svg width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + " " + H + '" role="group" aria-label="' + esc(spec.title || "Chart") + '">';
    ticks.forEach((t) => {
      const ty = y(t);
      h += '<line x1="' + M.l + '" x2="' + (W - M.r) + '" y1="' + ty + '" y2="' + ty + '" stroke="' + (t === 0 ? C.ink : C.grid) + '" stroke-width="1" shape-rendering="crispEdges"/>';
      h += '<text x="' + (M.l - 8) + '" y="' + (ty + 4) + '" text-anchor="end" fill="' + C.ink2 + '">' + tickFmt(t) + "</text>";
    });
    if (spec.unit) h += '<text x="' + 0 + '" y="12" fill="' + C.ink2 + '">' + esc(spec.unit) + "</text>";
    if (spec.ref) {
      const ry = y(spec.ref.value);
      h += '<line x1="' + M.l + '" x2="' + (W - M.r) + '" y1="' + ry + '" y2="' + ry + '" stroke="' + C.ink + '" stroke-width="1" shape-rendering="crispEdges"/>';
      h += '<text x="' + (W - M.r) + '" y="' + (ry - 6) + '" text-anchor="end" fill="' + C.ink + '">' + esc(narrow && spec.ref.short ? spec.ref.short : spec.ref.label) + "</text>";
    }
    cats.forEach((cat, j) => {
      const bx = M.l + j * band, gx = bx + (band - group) / 2;
      const aria = (spec.x ? spec.x + " " : "") + cat + ": " + series.map((s) => (s.roles ? "" : s.name + " ") + fmt(s.values[j]) + unit).join("; ");
      h += '<g class="band" data-j="' + j + '" tabindex="0" role="img" aria-label="' + esc(aria) + '">';
      h += '<rect class="band__hit" x="' + bx + '" y="' + M.t + '" width="' + band + '" height="' + ph + '" fill="transparent"/>';
      series.forEach((s, i) => {
        const v = s.values[j], x = gx + i * (barW + 2), by = y(v);
        h += '<rect x="' + x.toFixed(1) + '" y="' + by.toFixed(1) + '" width="' + Math.max(1, barW).toFixed(1) + '" height="' + Math.max(0, M.t + ph - by).toFixed(1) + '" rx="2" fill="' + COLOR[roleOf(s, j)] + '"/>';
        if (labels) h += '<text x="' + (x + barW / 2).toFixed(1) + '" y="' + (by - 6).toFixed(1) + '" text-anchor="middle" fill="' + (roleOf(s, j) === "mine" ? C.ink : C.ink2) + '"' + (roleOf(s, j) === "mine" ? ' font-weight="500"' : "") + ">" + fmt(v) + "</text>";
      });
      h += '<text x="' + (bx + band / 2) + '" y="' + (M.t + ph + 18) + '" text-anchor="middle" fill="' + C.ink + '">' + esc(cat) + "</text>";
      h += "</g>";
    });
    if (spec.x) h += '<text x="' + M.l + '" y="' + (H - 4) + '" fill="' + C.ink2 + '">' + esc(spec.x) + "</text>";
    h += "</svg>";
    plot.innerHTML = h + '<div class="chart__tip" hidden aria-hidden="true"></div>';

    // tooltips: hover or keyboard focus on a category
    const tip = plot.querySelector(".chart__tip");
    function show(j) {
      tip.innerHTML = "<b>" + esc((spec.x ? spec.x + " " : "") + cats[j]) + "</b>" + series.map((s) => {
        const role = roleOf(s, j);
        return '<p><span class="chart__sw" style="background:' + COLOR[role] + '"></span><span>' + esc(s.roles ? s.pointNames[j] : s.name) + "</span><span>" + fmt(s.values[j]) + esc(unit) + "</span></p>";
      }).join("");
      tip.hidden = false;
      const cx = M.l + (j + 0.5) * band, tw = tip.offsetWidth, th = tip.offsetHeight;
      const peak = Math.min.apply(null, series.map((s) => y(s.values[j])));
      tip.style.left = Math.min(Math.max(0, cx - tw / 2), W - tw) + "px";
      tip.style.top = Math.max(0, peak - th - 10) + "px";
    }
    const hide = () => { tip.hidden = true; };
    plot.querySelectorAll(".band").forEach((g) => {
      const j = +g.getAttribute("data-j");
      g.addEventListener("pointerenter", () => show(j));
      g.addEventListener("focus", () => show(j));
      g.addEventListener("pointerleave", hide);
      g.addEventListener("blur", hide);
    });
  }

  function legend(fig) {
    let spec;
    try { spec = JSON.parse(fig.getAttribute("data-chart")); } catch (e) { return; }
    const ul = fig.querySelector(".chart__legend");
    if (!ul || ul.children.length) return;
    const items = spec.legend || spec.series.map((s) => ({ name: s.name, role: s.role }));
    ul.innerHTML = items.map((it) => '<li><span class="chart__sw" style="background:' + COLOR[it.role] + '"></span>' + esc(it.name) + "</li>").join("");
  }

  const figs = Array.from(document.querySelectorAll("figure.chart[data-chart]"));
  figs.forEach((f) => { legend(f); draw(f); });
  const widths = new Map();
  function redraw() {
    figs.forEach((f) => {
      const p = f.querySelector(".chart__plot"), w = p ? p.clientWidth : 0;
      if (widths.get(f) !== w) { widths.set(f, w); draw(f); }
    });
  }
  let t = 0;
  const onResize = () => { clearTimeout(t); t = setTimeout(redraw, 120); };
  if ("ResizeObserver" in window) figs.forEach((f) => new ResizeObserver(onResize).observe(f)); else window.addEventListener("resize", onResize);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") document.querySelectorAll(".chart__tip").forEach((tp) => { tp.hidden = true; }); });
})();

#!/usr/bin/env python3
"""Build the data and the generated parts of the blackwell-gemm pages.

Inputs (copied from the blackwell-gemm repo and the Nsight Compute exports):
    scripts/gemm_src/README.md                      kernel list ("What changed")
    scripts/gemm_src/results/<gpu>.csv              benchmark numbers
    scripts/gemm_src/results/<gpu>_gpu.txt          the machine
    scripts/gemm_src/ncu_text/<gpu>_<NN>_<kernel>_4096.txt
                                                    Nsight Compute "Details" page as text

Outputs:
    blackwell-gemm/data/bench.json                  4096 results per GPU
    blackwell-gemm/data/ncu.json                    every parsed report
    generated regions inside blackwell-gemm/index.html and
    blackwell-gemm/<NN-slug>/index.html, between
        <!-- gemm:NAME -->  and  <!-- /gemm:NAME -->
    Everything outside those markers is hand-written and left alone.

Nothing is estimated: a value or section missing from a file is left out.
Run from anywhere (stdlib only):
    python3 scripts/build_gemm.py
"""

import csv
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "scripts", "gemm_src")
OUT = os.path.join(ROOT, "blackwell-gemm")
SIZE = "4096"
REPO = "https://github.com/VrajPatel105/blackwell-gemm"
RELEASE = REPO + "/releases/tag/v0.1-fp32"

GPUS = [
    {"id": "rtx5080_laptop", "label": "RTX 5080 Laptop"},
    {"id": "b200", "label": "NVIDIA B200"},
]
# The CSV "name" column for each kernel number, as written in the repo.
CSV_NAMES = ["naive", "coalesced", "tiling", "1d_thread", "2d_thread", "vectorized_smem_float4", "warp_tiling"]

esc = lambda s: html.escape(str(s), quote=True)
warnings_out = []


def warn(msg):
    warnings_out.append(msg)
    print("note:", msg, file=sys.stderr)


# --------------------------------------------------------------------------
# Sources
# --------------------------------------------------------------------------
def read_kernels():
    """The README's kernel table: number, name and what changed."""
    text = open(os.path.join(SRC, "README.md"), encoding="utf-8").read()
    rows = re.findall(r"^\| (\d\d) \| ([^|]+?) \| ([^|]+?) \|$", text, re.M)
    kernels = []
    for num, name, changed in rows:
        slug = num + "-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        kernels.append({"num": num, "name": name.strip(), "changed": changed.strip(), "slug": slug})
    if len(kernels) != 7:
        sys.exit("expected 7 kernels in README.md, found %d" % len(kernels))
    return kernels


def read_bench(gpu):
    path = os.path.join(SRC, "results", gpu + ".csv")
    rows = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["M"] == r["N"] == r["K"] == SIZE:
                rows[int(r["id"])] = r
    out = {"kernels": [], "cublas_tflops": None}
    for i, name in enumerate(CSV_NAMES):
        r = rows.get(i)
        if not r or r["name"] != name:
            warn("%s.csv: no %s row for kernel %02d" % (gpu, SIZE, i))
            out["kernels"].append(None)
            continue
        out["kernels"].append({"tflops": r["tflops"], "pct_cublas": r["pct_cublas"], "ms": r["ms"], "pass": r["pass"]})
        out["cublas_tflops"] = out["cublas_tflops"] or r["cublas_tflops"]
    return out


def read_machine(gpu):
    path = os.path.join(SRC, "results", gpu + "_gpu.txt")
    lines = open(path, encoding="utf-8").read().splitlines()
    m = {}
    for i, line in enumerate(lines):
        if line.startswith("name, driver_version") and i + 1 < len(lines):
            parts = [p.strip() for p in lines[i + 1].split(",")]
            m["name"], m["driver"], m["memory"] = parts[0], parts[1], parts[2]
        mm = re.match(r"Cuda compilation tools, release ([\d.]+)", line)
        if mm:
            m["nvcc"] = mm.group(1)
    return m


# --------------------------------------------------------------------------
# Nsight Compute text export parser
# --------------------------------------------------------------------------
SEP = re.compile(r"^\s+-{3,}(?: +-{3,})+\s*$")
NOTE_START = re.compile(r"^    (OPT|INF|WRN|ERR)   (.*)$")
SPEEDUP = re.compile(r"^Est\. (Local )?Speedup: ([\d.]+)%$")


def spans(sep_line):
    return [(m.start(), m.end()) for m in re.finditer(r"-+", sep_line)]


def cut(line, sp):
    """Slice a table row by the dash spans of its separator line."""
    cells = []
    for k, (a, b) in enumerate(sp):
        end = sp[k + 1][0] if k + 1 < len(sp) else len(line)
        cells.append(line[a:max(b, end)].strip())
    return cells


def parse_ncu(path):
    lines = open(path, encoding="utf-8").read().splitlines()
    rep = {"file": os.path.basename(path), "sections": [], "unparsed": []}
    head = lines[1].strip() if len(lines) > 1 else ""
    m = re.match(r"^(.*?) \((\d+, \d+, \d+)\)x\((\d+, \d+, \d+)\), .*?CC ([\d.]+)$", head)
    if m:
        rep["kernel"], rep["grid"], rep["block"], rep["cc"] = m.group(1), m.group(2), m.group(3), m.group(4)
    else:
        rep["unparsed"].append("line 2 (kernel and launch configuration)")

    sec = None
    i = 2
    while i < len(lines):
        line = lines[i]
        if line.startswith("    Section: "):
            sec = {"name": line[len("    Section: "):].strip(), "metrics": [], "notes": []}
            rep["sections"].append(sec)
            i += 1
            continue
        if sec is None or not line.strip():
            i += 1
            continue
        if re.match(r"^    -----\s+-+\s*$", line):  # divider between two notes
            i += 1
            continue
        if SEP.match(line):
            # a metric table: sep, header, sep, rows..., sep
            sp = spans(line)
            hdr = cut(lines[i + 1], sp) if i + 1 < len(lines) else []
            if hdr[:1] != ["Metric Name"] or i + 2 >= len(lines) or not SEP.match(lines[i + 2]):
                rep["unparsed"].append("%s: table at line %d" % (sec["name"], i + 1))
                i += 1
                continue
            i += 3
            while i < len(lines) and not SEP.match(lines[i]):
                c = cut(lines[i], sp)
                if len(c) == 3 and c[0]:
                    sec["metrics"].append({"name": c[0], "unit": c[1], "value": c[2]})
                elif lines[i].strip():
                    rep["unparsed"].append("%s: row %r" % (sec["name"], lines[i].strip()))
                i += 1
            i += 1
            continue
        nm = NOTE_START.match(line)
        if nm:
            kind, first = nm.group(1), nm.group(2).strip()
            body = []
            i += 1
            while i < len(lines) and lines[i].startswith("          ") and lines[i].strip():
                body.append(lines[i].strip())
                i += 1
            note = {"type": kind}
            sm = SPEEDUP.match(first)
            if sm:
                note["speedup"] = sm.group(2)
                note["speedup_label"] = "Est. Local Speedup" if sm.group(1) else "Est. Speedup"
            else:
                body.insert(0, first)
            note["text"] = " ".join(body)
            sec["notes"].append(note)
            continue
        rep["unparsed"].append("%s: line %d %r" % (sec["name"], i + 1, line.strip()[:60]))
        i += 1
    return rep


def metric(rep, section, name):
    for s in rep["sections"]:
        if s["name"] == section:
            for mt in s["metrics"]:
                if mt["name"] == name:
                    return mt
    return None


def note_title(text):
    """The note's first sentence, or the clause before a leading 'X: Y' colon."""
    first = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text, maxsplit=1)[0]
    cm = re.match(r"^([^:]{8,90}): [A-Z]", first)
    return cm.group(1) if cm else first


def key_pct(text):
    t = re.sub(r"\(https?://[^)]*\)", "", text)
    m = re.search(r"(\d+(?:\.\d+)?)%", t)
    return m.group(1) if m else None


def summarize(rep):
    s = {}
    for key, sec, name in [
        ("compute", "GPU Speed Of Light Throughput", "Compute (SM) Throughput"),
        ("memory", "GPU Speed Of Light Throughput", "Memory Throughput"),
        ("duration", "GPU Speed Of Light Throughput", "Duration"),
        ("regs", "Launch Statistics", "Registers Per Thread"),
        ("occ_achieved", "Occupancy", "Achieved Occupancy"),
        ("occ_theoretical", "Occupancy", "Theoretical Occupancy"),
        ("cpi", "Warp State Statistics", "Warp Cycles Per Issued Instruction"),
    ]:
        mt = metric(rep, sec, name)
        if mt:
            s[key] = mt

    units = []
    for label, name in [("L1/TEX", "L1/TEX Cache Throughput"), ("L2", "L2 Cache Throughput"), ("DRAM", "DRAM Throughput")]:
        mt = metric(rep, "GPU Speed Of Light Throughput", name)
        if mt:
            units.append((float(mt["value"]), label, mt["value"]))
    if units:
        units.sort(key=lambda u: -u[0])
        s["busiest"] = {"unit": units[0][1], "value": units[0][2]}

    warns = []
    for sec in rep["sections"]:
        for n in sec["notes"]:
            if n["type"] in ("OPT", "WRN", "ERR"):
                w = {"section": sec["name"], "title": note_title(n["text"]), "text": n["text"]}
                if key_pct(n["text"]):
                    w["pct"] = key_pct(n["text"])
                if "speedup" in n:
                    w["speedup"], w["speedup_label"] = n["speedup"], n["speedup_label"]
                warns.append(w)
    warns.sort(key=lambda w: -float(w.get("speedup", -1)))  # stable: no-speedup notes keep report order, last
    s["warnings"] = warns

    for sec in rep["sections"]:
        if sec["name"] != "Warp State Statistics":
            continue
        t = " ".join(n["text"] for n in sec["notes"])
        a = re.search(r"spends ([\d.]+) cycles being stalled (.*?)\. ", t)
        b = re.search(r"represents about ([\d.]+)% of the total average of ([\d.]+) cycles", t)
        if a:
            s["stall"] = {"reason": a.group(2), "cycles": a.group(1)}
            if b:
                s["stall"]["pct"], s["stall"]["of_cycles"] = b.group(1), b.group(2)

    limits = []
    for sec in rep["sections"]:
        if sec["name"] == "Occupancy":
            for mt in sec["metrics"]:
                if mt["name"].startswith("Block Limit "):
                    limits.append({"name": mt["name"][len("Block Limit "):], "value": mt["value"]})
    if limits:
        lo = min(float(l["value"]) for l in limits)
        for l in limits:
            l["binding"] = float(l["value"]) == lo
        s["limits"] = limits
    return s


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def tf(v):
    return "%.2f" % float(v)


def with_unit(mt):
    u = mt["unit"]
    if not u:
        return mt["value"]
    return mt["value"] + ("%" if u == "%" else " " + u)


def render_bench_tiles(k, bench):
    h = '<div class="x-proof x-proof--4">\n'
    for g in GPUS:
        b = bench[g["id"]]
        r = b["kernels"][int(k["num"])]
        if not r:
            continue
        h += '      <div><b>%s TFLOP/s</b><small>%s, %s x %s FP32</small></div>\n' % (tf(r["tflops"]), esc(g["label"]), SIZE, SIZE)
        h += '      <div><b>%s%%</b><small>Of cuBLAS on %s (%s TFLOP/s)</small></div>\n' % (esc(r["pct_cublas"]), esc(g["label"]), tf(b["cublas_tflops"]))
    return h + "    </div>"


def render_chart(gpu, kernels, bench):
    b = bench[gpu["id"]]
    cats, vals, rows = [], [], []
    for k in kernels:
        r = b["kernels"][int(k["num"])]
        if not r:
            continue
        cats.append(k["num"])
        vals.append(round(float(r["tflops"]), 2))
        rows.append((k, r))
    spec = {
        "title": "TFLOP/s per kernel at %s, %s" % (SIZE, gpu["label"]),
        "x": "kernel", "unit": "TFLOP/s", "decimals": 2, "categories": cats,
        "ref": {"value": round(float(b["cublas_tflops"]), 2), "label": "cuBLAS %s TFLOP/s" % tf(b["cublas_tflops"]), "short": "cuBLAS %s" % tf(b["cublas_tflops"])},
        "series": [{"name": "My kernels", "role": "mine", "values": vals}],
    }
    attr = json.dumps(spec, ensure_ascii=False, separators=(",", ":"))
    attr = attr.replace("&", "&amp;").replace("<", "&lt;").replace("'", "&#39;")
    h = "<figure class=\"chart\" data-chart='%s'>\n" % attr
    h += '      <p class="chart__title">%s</p>\n' % esc(gpu["label"])
    h += '      <ul class="chart__legend"></ul>\n      <div class="chart__plot"></div>\n'
    h += '      <figcaption>FP32, %s x %s x %s. The line is cuBLAS on the same GPU.</figcaption>\n    </figure>\n' % (SIZE, SIZE, SIZE)
    h += '    <div class="table-wrap">\n      <table class="data">\n'
    h += '        <caption>%s · %s x %s x %s · FP32</caption>\n' % (esc(gpu["label"]), SIZE, SIZE, SIZE)
    h += '        <thead><tr><th scope="col">Kernel</th><th scope="col" class="num">TFLOP/s</th><th scope="col" class="num">% of cuBLAS</th></tr></thead>\n        <tbody>\n'
    for k, r in rows:
        h += '          <tr><th scope="row">%s %s</th><td class="num is-mine">%s</td><td class="num">%s%%</td></tr>\n' % (k["num"], esc(k["name"]), tf(r["tflops"]), esc(r["pct_cublas"]))
    h += '          <tr><th scope="row">cuBLAS</th><td class="num is-base">%s</td><td class="num">100%%</td></tr>\n' % tf(b["cublas_tflops"])
    h += "        </tbody>\n      </table>\n    </div>"
    return h


def page_exists(k):
    return os.path.isfile(os.path.join(OUT, k["slug"], "index.html"))


def render_kernel_list(kernels):
    h = '<ol class="g-kernels">\n'
    for k in kernels:
        name = "%s · %s" % (k["num"], esc(k["name"]))
        if page_exists(k):
            name = '<a href="%s/">%s</a>' % (k["slug"], name)
        else:
            name = '<span>%s</span> <small>page coming</small>' % name
        h += "      <li>%s<p>%s</p></li>\n" % (name, esc(k["changed"]))
    return h + "    </ol>"


def render_pager(kernels, idx):
    def link(k, rel):
        label = "%s · %s" % (k["num"], esc(k["name"]))
        if page_exists(k):
            return '<a class="g-pager__%s" href="../%s/" rel="%s"><small>%s</small>%s</a>' % (rel, k["slug"], rel, "Previous" if rel == "prev" else "Next", label)
        return '<span class="g-pager__%s is-off"><small>%s, page coming</small>%s</span>' % (rel, "Previous" if rel == "prev" else "Next", label)

    h = '<nav class="g-pager" aria-label="Kernels">\n'
    if idx > 0:
        h += "      " + link(kernels[idx - 1], "prev") + "\n"
    else:
        h += '      <a class="g-pager__prev" href="../" rel="prev"><small>Previous</small>Overview</a>\n'
    if idx + 1 < len(kernels):
        h += "      " + link(kernels[idx + 1], "next") + "\n"
    else:
        h += '      <a class="g-pager__next" href="../"><small>Back to</small>Overview</a>\n'
    return h + "    </nav>"


def render_panel(gpu, rep, s, active):
    gid = gpu["id"]
    h = '<div class="g-panel" id="p-%s" data-gpu="%s" role="tabpanel" aria-labelledby="t-%s">\n' % (gid, gid, gid)
    h += '      <h3 class="g-panel__h">%s</h3>\n' % esc(gpu["label"])
    meta = []
    if rep.get("grid"):
        meta.append("grid (%s) · block (%s) · CC %s" % (rep["grid"], rep["block"], rep["cc"]))
    if s.get("duration"):
        meta.append("duration " + with_unit(s["duration"]))
    meta.append("source: " + rep["file"])
    h += '      <p class="g-meta">%s</p>\n' % " · ".join(esc(m) for m in meta)

    # stat tiles
    tiles = []
    if s.get("compute"):
        tiles.append((s["compute"]["value"] + "%", "Compute (SM) throughput"))
    if s.get("memory"):
        tiles.append((s["memory"]["value"] + "%", "Memory throughput"))
    if s.get("busiest"):
        tiles.append(("%s %s%%" % (s["busiest"]["unit"], s["busiest"]["value"]), "Busiest memory unit (of L1/TEX, L2, DRAM)"))
    if s.get("regs"):
        tiles.append((s["regs"]["value"], "Registers per thread"))
    if s.get("occ_achieved") and s.get("occ_theoretical"):
        tiles.append(("%s%% / %s%%" % (s["occ_achieved"]["value"], s["occ_theoretical"]["value"]), "Occupancy, achieved / theoretical"))
    if tiles:
        h += '      <div class="g-tiles">\n'
        for v, label in tiles:
            h += '        <div><b>%s</b><small>%s</small></div>\n' % (esc(v), esc(label))
        h += "      </div>\n"

    # warnings
    if s["warnings"]:
        h += '      <h4>Profiler warnings <small>most significant first</small></h4>\n'
        h += '      <div class="table-wrap">\n        <table class="data g-warn">\n'
        h += '          <thead><tr><th scope="col">Warning</th><th scope="col" class="num">Key %</th><th scope="col" class="num">Est. speedup</th></tr></thead>\n          <tbody>\n'
        for w in s["warnings"]:
            sp = ""
            if "speedup" in w:
                sp = w["speedup"] + "%" + (" <small>local</small>" if w["speedup_label"] == "Est. Local Speedup" else "")
            h += '            <tr><th scope="row">%s<small>%s</small></th><td class="num">%s</td><td class="num">%s</td></tr>\n' % (
                esc(w["title"]), esc(w["section"]), esc(w["pct"] + "%") if "pct" in w else "", sp)
        h += "          </tbody>\n        </table>\n      </div>\n"

    # warp state + occupancy
    h += '      <div class="g-two">\n'
    if s.get("cpi") or s.get("stall"):
        h += '        <div class="g-box">\n          <h4>Warp state</h4>\n          <dl class="g-dl">\n'
        if s.get("cpi"):
            h += "            <div><dt>Warp cycles per issued instruction</dt><dd>%s</dd></div>\n" % esc(s["cpi"]["value"])
        if s.get("stall"):
            st = s["stall"]
            extra = "%s cycles per warp" % st["cycles"]
            if st.get("pct"):
                extra += ", about %s%% of the %s cycles between two issued instructions" % (st["pct"], st["of_cycles"])
            h += "            <div><dt>Top stall reason (profiler note)</dt><dd>Stalled %s<small>%s</small></dd></div>\n" % (esc(st["reason"]), esc(extra))
        h += "          </dl>\n        </div>\n"
    if s.get("limits"):
        shown = [l for l in s["limits"] if l["name"] in ("Registers", "Warps", "Shared Mem") or l["binding"]]
        h += '        <div class="g-box">\n          <h4>Occupancy: block limits</h4>\n          <dl class="g-dl">\n'
        for l in shown:
            mark = ' <span class="g-chip">binding</span>' if l["binding"] else ""
            h += "            <div%s><dt>%s</dt><dd>%s block%s%s</dd></div>\n" % (
                ' class="is-binding"' if l["binding"] else "", esc(l["name"]), esc(l["value"]), "" if l["value"] == "1" else "s", mark)
        h += '          </dl>\n          <p class="g-fine">Blocks per SM each resource allows. The lowest one sets occupancy.</p>\n        </div>\n'
    h += "      </div>\n"

    # full report
    h += '      <h4>Full report <small>%d sections, in report order</small></h4>\n      <div class="g-sections">\n' % len(rep["sections"])
    for sec in rep["sections"]:
        count = []
        if sec["metrics"]:
            count.append("%d metric%s" % (len(sec["metrics"]), "" if len(sec["metrics"]) == 1 else "s"))
        if sec["notes"]:
            count.append("%d note%s" % (len(sec["notes"]), "" if len(sec["notes"]) == 1 else "s"))
        h += '        <details>\n          <summary>%s <small>%s</small></summary>\n          <div class="details-body">\n' % (esc(sec["name"]), esc(" · ".join(count)))
        if sec["metrics"]:
            h += '            <div class="table-wrap"><table class="data g-metrics"><thead><tr><th scope="col">Metric</th><th scope="col" class="num">Value</th></tr></thead><tbody>\n'
            for mt in sec["metrics"]:
                h += '              <tr><th scope="row">%s</th><td class="num">%s</td></tr>\n' % (esc(mt["name"]), esc(with_unit(mt)))
            h += "            </tbody></table></div>\n"
        for n in sec["notes"]:
            tag = n["type"] + (" · %s: %s%%" % (n["speedup_label"], n["speedup"]) if "speedup" in n else "")
            h += '            <p class="g-note"><span class="eyebrow">%s</span>%s</p>\n' % (esc(tag), esc(n["text"]))
        h += "          </div>\n        </details>\n"
    h += "      </div>\n    </div>"
    return h


def render_dashboard(k, reports, summaries):
    present = [g for g in GPUS if g["id"] in reports]
    h = '<div class="g-dash" data-gemm-dash>\n'
    h += '    <div class="g-switch" role="tablist" aria-label="GPU" hidden>\n'
    for i, g in enumerate(present):
        h += '      <button type="button" role="tab" id="t-%s" aria-controls="p-%s" aria-selected="%s" data-gpu="%s">%s</button>\n' % (
            g["id"], g["id"], "true" if i == 0 else "false", g["id"], esc(g["label"]))
    h += "    </div>\n"
    for i, g in enumerate(present):
        h += "    " + render_panel(g, reports[g["id"]], summaries[g["id"]], i == 0) + "\n"
    h += '    <p class="g-fine">Parsed from the Nsight Compute Details page exported as text, at %s x %s. The two GPUs were profiled with different Nsight Compute versions, so their reports do not have identical sections. The original <code>.ncu-rep</code> files are in the <a href="%s" target="_blank" rel="noopener">v0.1-fp32 release</a> and open in the Nsight Compute UI.</p>\n' % (SIZE, SIZE, RELEASE)
    return h + "  </div>"


# --------------------------------------------------------------------------
# Region replacement
# --------------------------------------------------------------------------
def fill(path, regions):
    src = open(path, encoding="utf-8").read()
    out = src
    for name, body in regions.items():
        pat = re.compile(r"(<!-- gemm:%s -->)(.*?)(<!-- /gemm:%s -->)" % (re.escape(name), re.escape(name)), re.S)
        if not pat.search(out):
            continue
        out = pat.sub(lambda m: m.group(1) + "\n    " + body + "\n    " + m.group(3), out)
    if out != src:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(out)
        print("wrote", os.path.relpath(path, ROOT))


def main():
    kernels = read_kernels()
    bench = {g["id"]: read_bench(g["id"]) for g in GPUS}
    machines = {g["id"]: read_machine(g["id"]) for g in GPUS}

    ncu = {}
    for k in kernels:
        for g in GPUS:
            pat = re.compile(r"^%s_%s_.*_%s\.txt$" % (g["id"], k["num"], SIZE))
            files = [f for f in sorted(os.listdir(os.path.join(SRC, "ncu_text"))) if pat.match(f)]
            if not files:
                warn("no Nsight text export for %s kernel %s" % (g["id"], k["num"]))
                continue
            rep = parse_ncu(os.path.join(SRC, "ncu_text", files[0]))
            for u in rep["unparsed"]:
                warn("%s: could not parse %s" % (rep["file"], u))
            rep["summary"] = summarize(rep)
            ncu.setdefault(k["num"], {})[g["id"]] = rep

    os.makedirs(os.path.join(OUT, "data"), exist_ok=True)
    with open(os.path.join(OUT, "data", "bench.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"size": SIZE, "kernels": kernels, "machines": machines, "gpus": bench}, f, indent=1)
    with open(os.path.join(OUT, "data", "ncu.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(ncu, f, indent=1)

    over = os.path.join(OUT, "index.html")
    if os.path.isfile(over):
        regions = {"kernels": render_kernel_list(kernels)}
        for g in GPUS:
            regions["chart-" + g["id"]] = render_chart(g, kernels, bench)
        fill(over, regions)

    for idx, k in enumerate(kernels):
        page = os.path.join(OUT, k["slug"], "index.html")
        if not os.path.isfile(page):
            continue
        reps = ncu.get(k["num"], {})
        fill(page, {
            "bench": render_bench_tiles(k, bench),
            "dashboard": render_dashboard(k, reps, {g: reps[g]["summary"] for g in reps}),
            "pager": render_pager(kernels, idx),
        })
    if not warnings_out:
        print("parsed everything; nothing left over")


if __name__ == "__main__":
    main()

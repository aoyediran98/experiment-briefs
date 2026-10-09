#!/usr/bin/env python3
"""Render a pre-registered experiment brief as a static HTML page.

Usage:  python3 scripts/make_brief.py input.json
Writes: briefs/<date>-<slug>.html and updates briefs/index.json
Prints: the relative path of the new brief.

The statistics are computed HERE, deterministically, from the numbers in
input.json. The written sections (metrics, criteria, variants) are authored
by Claude and passed in; the script never changes the numbers.
"""
import json, math, re, sys, datetime, html, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

# ---------- statistics ----------
def z(p):
    """Inverse normal CDF (Acklam approximation)."""
    a = [-3.969683028665376e1, 2.209460984245205e2, -2.759285104469687e2, 1.383577518672690e2, -3.066479806614716e1, 2.506628277459239]
    b = [-5.447609879822406e1, 1.615858368580409e2, -1.556989798598866e2, 6.680131188771972e1, -1.328068155288572e1]
    c = [-7.784894002430293e-3, -3.223964580411365e-1, -2.400758277161838, -2.549732539343734, 4.374664141464968, 2.938163982698783]
    d = [7.784695709041462e-3, 3.224671290700398e-1, 2.445134137142996, 3.754408661907416]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p <= ph:
        q = p - 0.5; r = q*q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)

def sample_size(p1, rel, alpha, power):
    """Per-arm sample size, two-proportion z-test, two-sided."""
    p2 = p1 * (1 + rel)
    if not 0 < p2 < 1:
        raise ValueError("target conversion out of range")
    pb = (p1 + p2) / 2
    num = z(1 - alpha/2) * math.sqrt(2*pb*(1-pb)) + z(power) * math.sqrt(p1*(1-p1) + p2*(1-p2))
    return math.ceil(num*num / (p2 - p1)**2)

def mde_for_weeks(p1, weekly, arms, weeks, alpha, power):
    per_arm = weekly * weeks / arms
    lo, hi = 0.001, 3.0
    for _ in range(60):
        mid = (lo + hi) / 2
        try:
            n = sample_size(p1, mid, alpha, power)
        except ValueError:
            n = float("inf")
        if n > per_arm: lo = mid
        else: hi = mid
    return hi

# ---------- rendering ----------
def esc(s): return html.escape(str(s or ""))
def li(items): return "".join(f"<li>{esc(x)}</li>" for x in (items or []))
def slugify(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]

def main(path):
    inp = json.loads(pathlib.Path(path).read_text())
    p1 = float(inp["baseline_cr"]) / 100
    rel = float(inp["mde_relative"]) / 100
    weekly = int(inp["weekly_visitors"])
    arms = int(inp.get("arms", 2))
    alpha = float(inp.get("alpha", 0.05))
    power = float(inp.get("power", 0.8))

    n = sample_size(p1, rel, alpha, power)
    total = n * arms
    raw_weeks = total / weekly
    weeks = max(2, math.ceil(raw_weeks))
    p2 = p1 * (1 + rel)
    extra = round(weekly / arms * (p2 - p1))
    mde4 = mde_for_weeks(p1, weekly, arms, 4, alpha, power)

    if raw_weeks > 8:
        flag_cls, flag = "bad", f"At {weekly:,} visitors a week this needs {math.ceil(raw_weeks)} weeks, too long to hold clean. A {mde4*100:.1f}% relative effect is detectable in 4 weeks at this traffic; either accept that MDE, cut arms, or move the test up the funnel."
    elif raw_weeks > 4:
        flag_cls, flag = "warn", f"{math.ceil(raw_weeks)} weeks is workable but exposed to seasonality and campaign changes. End date is pre-registered; no peeking."
    else:
        flag_cls, flag = "ok", f"Feasible in {math.ceil(raw_weeks)} week(s) of traffic; run for {weeks} to cover full weekly cycles. Call only at the pre-set end date."

    today = datetime.date.today()
    slug = f"{today.isoformat()}-{slugify(inp['title'])}"
    b = inp["brief"]
    variants = "".join(
        f'<div class="variant"><div class="tag">{esc(v.get("name"))}</div><div class="why" style="margin:4px 0 6px;color:var(--fg)">{esc(v.get("change"))}</div><div class="hl">{esc(v.get("headline"))}</div><div>{esc(v.get("supporting"))}</div><div class="why">{esc(v.get("rationale"))}</div></div>'
        for v in b.get("variants", []))
    # ---------- visuals ----------
    # input "visuals": [{"path": "...png|jpg|gif|webp|svg|pdf", "caption": "...", "placement": "problem|control|variants|results"}]
    # Files are copied into briefs/assets/<slug>/ and rendered as figures in the chosen section.
    import shutil
    allowed = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf"}
    figs = {"problem": [], "control": [], "variants": [], "results": []}
    assets_dir = ROOT / "briefs" / "assets" / slug
    for v in inp.get("visuals", []):
        src = pathlib.Path(v["path"]).expanduser()
        if not src.is_absolute():
            src = (pathlib.Path(path).resolve().parent / src)
        if not src.exists():
            print(f"warning: visual not found, skipped: {src}", file=sys.stderr); continue
        if src.suffix.lower() not in allowed:
            print(f"warning: unsupported visual type, skipped: {src.name}", file=sys.stderr); continue
        if src.stat().st_size > 5_000_000:
            print(f"warning: {src.name} is over 5 MB, skipped (compress it first)", file=sys.stderr); continue
        assets_dir.mkdir(parents=True, exist_ok=True)
        dest = assets_dir / (slugify(src.stem)[:40] + src.suffix.lower())
        shutil.copyfile(src, dest)
        href = f"assets/{slug}/{dest.name}"
        cap = esc(v.get("caption", ""))
        if dest.suffix == ".pdf":
            body = f'<a class="file" href="{href}">Open PDF: {esc(src.name)}</a>'
        else:
            body = f'<img src="{href}" alt="{cap}" loading="lazy">'
        placement = v.get("placement", "variants")
        figs.setdefault(placement if placement in figs else "variants", []).append(f'<figure>{body}<figcaption>{cap}</figcaption></figure>')
    def fig_block(key):
        return f'<div class="figures">{"".join(figs[key])}</div>' if figs[key] else ""

    pm = b.get("primaryMetric") or {}
    if isinstance(pm, str): pm = {"name": pm}
    own = b.get("owners") or {}
    dr = b.get("decisionRules") or {}

    tpl = (ROOT / "templates" / "brief.html").read_text()
    page = tpl
    for k, v in {
        "TITLE": esc(inp["title"]), "DATE": today.strftime("%d %b %Y"), "AUTHOR": esc(inp.get("author", "")),
        "SURFACE": esc(inp.get("surface", "")), "HYPOTHESIS": esc(inp["hypothesis"]),
        "N": f"{n:,}", "TOTAL": f"{total:,}", "ARMS": str(arms), "WEEKS": str(weeks),
        "P1": f"{p1*100:.2f}%", "P2": f"{p2*100:.2f}%", "ABS": f"{(p2-p1)*100:.2f}", "MDE": f"{rel*100:.1f}%",
        "EXTRA": f"{extra:,}", "MDE4": f"{mde4*100:.1f}%", "WEEKLY": f"{weekly:,}",
        "ALPHA": str(alpha), "POWER": f"{power*100:.0f}%", "ZA": f"{z(1-alpha/2):.3f}", "ZB": f"{z(power):.3f}",
        "FLAG_CLASS": flag_cls, "FLAG": esc(flag),
        "PROBLEM": esc(b.get("problem")), "PRIOR": li(b.get("priorEvidence")),
        "CONTROL": esc(b.get("control")), "AUDIENCE": esc(b.get("audience")), "EXCLUDED": esc(b.get("excluded")),
        "ENTRY": esc(b.get("entryPoint")), "UNIT": esc(b.get("unitOfRandomisation")),
        "PRIMARY": esc(pm.get("name")), "NUMERATOR": esc(pm.get("numerator")), "DENOMINATOR": esc(pm.get("denominator")), "WINDOW": esc(pm.get("attributionWindow")),
        "SECONDARY": li(b.get("secondaryMetrics")), "GUARDRAILS": li(b.get("guardrails")), "MDE_RATIONALE": esc(b.get("mdeRationale")),
        "CRITERIA": esc(b.get("successCriteria")), "WIN": esc(dr.get("win")), "LOSS": esc(dr.get("loss")), "FLAT": esc(dr.get("flat")),
        "BASELINE_SOURCE": esc(b.get("baselineSource")), "ALLOCATION": esc(b.get("trafficAllocation")), "STOPPING": esc(b.get("stoppingRule")),
        "RISKS": li(b.get("risks")), "QA": li(b.get("qaChecks")), "SEGMENTS": li(b.get("segmentsToWatch")), "VARIANTS": variants,
        "FIG_PROBLEM": fig_block("problem"), "FIG_CONTROL": fig_block("control"), "FIG_VARIANTS": fig_block("variants"), "FIG_RESULTS": fig_block("results"),
        "OWNER_BUILD": esc(own.get("build")), "OWNER_ANALYSIS": esc(own.get("analysis")), "OWNER_DECISION": esc(own.get("decision")),
    }.items():
        page = page.replace("{{" + k + "}}", v)

    out = ROOT / "briefs" / f"{slug}.html"
    out.write_text(page)

    idx_path = ROOT / "briefs" / "index.json"
    idx = json.loads(idx_path.read_text()) if idx_path.exists() else []
    idx = [e for e in idx if e["slug"] != slug]
    idx.insert(0, {"slug": slug, "title": inp["title"], "date": today.isoformat(), "surface": inp.get("surface", ""),
                   "weeks": weeks, "n": n, "mde": f"{rel*100:.1f}%", "status": flag_cls})
    idx_path.write_text(json.dumps(idx, indent=2))
    print(f"briefs/{slug}.html")

if __name__ == "__main__":
    main(sys.argv[1])

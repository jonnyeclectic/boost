# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The `boost serve` HTTP catalog server — a small read-only view of the
installed skills plus JSON endpoints, extracted from the command layer.

The routing is a pure function (:func:`route`) that maps a request path to a
``(status, content_type, body)`` triple with no socket bound, so the whole
endpoint surface is unit-testable. :func:`serve_http` wires it into a threaded
stdlib HTTP server for the CLI.
"""
from __future__ import annotations

import contextlib
import errno
import html
import json
import re
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .. import __version__
from ..errors import BoostError
from . import catalog, lockfile, logs, paths, registry, store
from . import output as out

SKILL_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _validated_skill_name(name: str) -> str | None:
    """Return canonical trusted skill name, else None."""
    if not isinstance(name, str):
        return None
    if not SKILL_NAME_RE.fullmatch(name) or name in {".", ".."}:
        return None
    return name


#: Facet namespaces, in the order the rails render. `kind` first because it is
#: the one that changes what installing does to your machine.
FACET_ORDER = ("kind", "topic", "state", "tag", "tap")

#: Rows returned by one `/search.json` call. The catalogue reaches five figures
#: on a well-tapped machine, and a page that renders all of it stops being a
#: page. The response says `matched` so the cap is visible rather than implied.
SEARCH_LIMIT = 300

#: Taps drawn in the graph. Beyond a few hundred nodes a force layout is a
#: hairball whatever you do with it, so the tail is dropped by item count and
#: reported in `stats.dropped` — a silent cap would read as "this is all of it".
GRAPH_NODES = 300

#: Edges drawn, strongest first. Measured on a real 445-tap machine: 300 nodes
#: produce 5,181 overlaps, 55% of which are a single shared name — often a
#: coincidence on a generic one. Everything is drawn at that density and
#: nothing is legible; the strongest ~900 leave an average degree near six,
#: which is a graph you can read. `stats.overlaps` still reports the true
#: total, so the cap is visible rather than implied.
GRAPH_EDGES = 900

_CATEGORIES: dict | None = None


def registry_categories() -> dict:
    """Tap name -> curated category, from the shipped registries data.

    That taxonomy is decided from the names of the items a repo ships rather
    than from its README, and is pinned by
    ``tests/unit/test_registry_categories.py``. Reading it here rather than
    re-deriving one means the served facets and `boost registries` cannot
    disagree. Missing or malformed data reads as "no categories": a catalogue
    page must not fail to render because a data file moved.
    """
    global _CATEGORIES
    if _CATEGORIES is None:
        _CATEGORIES = {}
        try:
            raw = (Path(__file__).resolve().parent.parent
                   / "data" / "registries.json").read_text(encoding="utf-8")
            for row in json.loads(raw).get("registries", []):
                name, cat = row.get("name"), row.get("category")
                if name and cat:
                    _CATEGORIES[str(name)] = str(cat)
        except (OSError, ValueError, AttributeError, TypeError):
            _CATEGORIES = {}
    return _CATEGORIES


def _frontmatter_tags(meta) -> list:
    """``tags:`` off an item's own frontmatter — third-party YAML, so anything.

    A list and a comma string are both common in the wild, and everything else
    reads as "no tags". This runs inside the page render, so a single item with
    ``tags: {a: 1}`` in one of hundreds of taps must not blank the catalogue.
    """
    if not isinstance(meta, dict):
        return []
    raw = meta.get("tags")
    if isinstance(raw, str):
        raw = raw.split(",")
    if not isinstance(raw, (list, tuple)):
        return []
    return [str(t).strip().lower() for t in raw
            if isinstance(t, (str, int, float)) and str(t).strip()]


def entry_tags(entry: dict, *, installed=(), categories=None) -> list:
    """Facet tags for one catalog entry: namespaced, sorted, de-duplicated.

    The namespace is not decoration. Filters apply per namespace, and an
    unprefixed value makes a tap literally named ``skill`` indistinguishable
    from the kind — which is the sort of collision a third-party registry gets
    to choose for you.
    """
    cats = registry_categories() if categories is None else categories
    tap = str(entry.get("tap") or "")
    tags = {"kind:" + str(entry.get("kind") or "skill")}
    if tap:
        tags.add("tap:" + tap)
        cat = cats.get(tap)
        if cat:
            tags.add("topic:" + str(cat))
    if entry.get("curated"):
        tags.add("state:curated")
    if entry.get("name") in installed:
        tags.add("state:installed")
    tags.update("tag:" + t for t in _frontmatter_tags(entry.get("meta")))
    return sorted(tags)


def catalog_rows() -> list:
    """Every catalog entry as a display row: tags, install state, provenance.

    ``installed`` spans all three kinds. ``lockfile.installed()`` is skills
    only, and a rule shown as merely "available" while it is materialized into
    the reader's own CLAUDE.md would be a lie about the most invasive thing
    boost installs.
    """
    lock = lockfile.read()
    installed = {n for key in ("skills", "rules", "workflows")
                 for n in (lock.get(key) or {})}
    cats = registry_categories()
    return [{
        "name": str(e.get("name") or ""),
        "description": e.get("description") or "",
        "version": str(e.get("version", "0.0.0")),
        "tap": str(e.get("tap") or ""),
        "kind": str(e.get("kind") or "skill"),
        "curated": bool(e.get("curated")),
        "installed": e.get("name") in installed,
        "tags": entry_tags(e, installed=installed, categories=cats),
        "search_blob": e.get("search_blob") or "",
    } for e in catalog.all_entries()]


def facet_counts(rows) -> dict:
    """Namespace -> ``[(value, count)]``, commonest first then alphabetical."""
    from collections import Counter
    buckets: dict = {}
    for row in rows:
        for tag in row.get("tags", ()):
            ns, _, value = tag.partition(":")
            if value:
                buckets.setdefault(ns, Counter())[value] += 1
    ordered = sorted(buckets, key=lambda ns: (FACET_ORDER.index(ns)
                                              if ns in FACET_ORDER else 99, ns))
    return {ns: sorted(buckets[ns].items(), key=lambda kv: (-kv[1], kv[0]))
            for ns in ordered}


def search_rows(rows, query: str = "", tags=(), limit: int | None = None) -> list:
    """Tag-filter (AND), then rank by ``query``, then cap.

    Ranking is :func:`catalog.search` rather than a second scorer written for
    this page: it is the one the eval gate floors, and a catalogue that ranked
    differently from `boost search` would be a third answer to the same
    question. Rows carry the same keys it reads, so they pass straight through.
    """
    want = {t for t in tags if t}
    if want:
        rows = [r for r in rows if want <= set(r.get("tags", ()))]
    q = query.strip()
    if q:
        rows = [e for e, _ in catalog.search(q, rows)]
    return rows[:limit] if limit else rows


def _label_propagate(node_ids, weights, rounds: int = 8) -> dict:
    """Deterministic community labels over the weighted overlap graph.

    Label propagation rather than Louvain: a dozen lines, no dependency, and on
    a graph this sparse it lands on the groupings that are actually legible.
    Iteration order is sorted and ties break on the lowest label, so the same
    catalogue always draws the same picture — which is the property that makes
    the graph testable at all.
    """
    from collections import Counter
    adj: dict = {n: [] for n in node_ids}
    for (a, b), w in weights.items():
        adj[a].append((b, w))
        adj[b].append((a, w))
    label = {n: i for i, n in enumerate(node_ids)}
    for _ in range(rounds):
        changed = False
        for n in node_ids:
            if not adj[n]:
                continue
            tally: Counter = Counter()
            for m, w in adj[n]:
                tally[label[m]] += w
            best = min(tally.items(), key=lambda kv: (-kv[1], kv[0]))[0]
            if best != label[n]:
                label[n] = best
                changed = True
        if not changed:
            break
    return label


def graph_data(rows, *, max_nodes: int | None = None) -> dict:
    """A graphify-shaped view of the catalogue: taps as nodes, overlap as edges.

    **Nodes are taps, not items.** A node per item is five figures on a real
    machine — unrenderable, and it draws the one structure that is already a
    list two clicks away. What a tap-level graph shows is the structure a table
    cannot: which registries carry the same things. ``code-reviewer`` ships
    from thirteen different taps, and that is the edge.

    **A repeat inside one tap is not an overlap.** Registries increasingly ship
    a copy per agent, so `holders` is a set — otherwise the commonest shape in
    the catalogue would draw every node bonded to itself.

    The payload is ``{nodes, edges, communities-on-nodes, stats}``, which is the
    shape graphify's own ``graph.json`` uses, so the endpoint can be fed to it
    rather than only to the tab that ships here.
    """
    from collections import Counter
    max_nodes = GRAPH_NODES if max_nodes is None else max_nodes
    by_tap: dict = {}
    for r in rows:
        if r.get("tap"):
            by_tap.setdefault(r["tap"], []).append(r)
    ranked = sorted(by_tap.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    kept = dict(ranked[:max_nodes])
    holders: dict = {}
    for tap, items in kept.items():
        for r in items:
            holders.setdefault(r["name"], set()).add(tap)
    weights: Counter = Counter()
    for taps in holders.values():
        if len(taps) < 2:
            continue
        ordered = sorted(taps)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1:]:
                weights[(a, b)] += 1
    strongest = sorted(weights.items(), key=lambda kv: (-kv[1], kv[0]))[:GRAPH_EDGES]
    communities = _label_propagate(sorted(kept), dict(strongest))
    cats = registry_categories()
    nodes = [{"id": tap,
              "label": tap.split("/")[-1],
              "tap": tap,
              "topic": cats.get(tap, "uncategorised"),
              "size": len(items),
              "installed": sum(1 for r in items if r.get("installed")),
              "kinds": dict(Counter(r.get("kind", "skill") for r in items)),
              "community": communities[tap]}
             for tap, items in sorted(kept.items())]
    links = [{"source": a, "target": b, "weight": w, "relation": "shares-items"}
             for (a, b), w in sorted(strongest)]
    # NetworkX node-link JSON, which is the shape graphify's own graph.json
    # uses — `links` rather than `edges`, with `directed`/`multigraph` and a
    # graph-level attribute dict. That makes this endpoint loadable by
    # `networkx.node_link_graph` and by graphify's tooling rather than merely
    # resembling it, which is the difference between a compatible format and a
    # similar one.
    return {"directed": False, "multigraph": False,
            "graph": {"name": "boost catalogue",
                      "taps": len(ranked), "shown": len(kept),
                      "dropped": len(ranked) - len(kept),
                      "items": len(rows), "overlaps": len(weights),
                      "links_shown": len(links)},
            "nodes": nodes, "links": links}


_ROWS_CACHE: dict = {}


def _catalog_fingerprint():
    """A cheap signal that the on-disk catalogue moved under a running server.

    Count, newest mtime and total size of the tap caches. `boost update` in
    another terminal rewrites one of those files, which changes all three; a
    server that cached forever would serve a catalogue the machine no longer
    has, and one that cached nothing would rebuild 71k rows per keystroke.
    """
    try:
        stats = [f.stat() for f in paths.cache_dir().glob("*.json")]
        # The lock file too, not only the tap caches. `installed` is a column
        # on every row, and a `boost install` in another terminal changes it
        # without touching a single catalog cache.
        with contextlib.suppress(OSError):
            stats.append(paths.lockfile_path().stat())
    except OSError:
        return ()
    return (len(stats), max((s.st_mtime_ns for s in stats), default=0),
            sum(s.st_size for s in stats))


def cached_view() -> tuple:
    """``(rows, facets)`` for the current catalogue, rebuilt only when it moves.

    Measured on a real machine: 71,695 rows take 0.54s to build and 0.12s to
    facet. That is per request, and the search box issues one per keystroke —
    so without this the page is unusable at exactly the catalogue size that
    makes it worth having.
    """
    fp = _catalog_fingerprint()
    if _ROWS_CACHE.get("fp") != fp or "rows" not in _ROWS_CACHE:
        rows = catalog_rows()
        _ROWS_CACHE.clear()
        _ROWS_CACHE.update(fp=fp, rows=rows, facets=facet_counts(rows))
    return _ROWS_CACHE["rows"], _ROWS_CACHE["facets"]


def cached_graph() -> dict:
    """The tap graph for the current catalogue, cached on the same signal."""
    rows, _ = cached_view()
    if "graph" not in _ROWS_CACHE:
        _ROWS_CACHE["graph"] = graph_data(rows)
    return _ROWS_CACHE["graph"]


def public_row(row: dict) -> dict:
    """A row without the search blob, which is index fuel and not display data."""
    return {k: v for k, v in row.items() if k != "search_blob"}


# The page is built by token substitution rather than %-formatting or .format():
# the CSS is full of bare `%` and the JS is full of braces, and both would have
# to be escaped into unreadability to survive either one.
_PAGE_CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
  --bg:#0b0d11; --panel:#12161d; --panel-2:#161b23; --line:#232a35;
  --fg:#e7ebf2; --dim:#8d97a8; --faint:#5c6675;
  --accent:#6cc2ff; --skill:#6cc2ff; --rule:#ffb454; --workflow:#c08bff;
  --ok:#5fd39b; --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px rgba(0,0,0,.28);
  --r:10px; --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
  --sans:system-ui,-apple-system,"Segoe UI",Inter,Roboto,sans-serif;
}
@media (prefers-color-scheme:light){:root{
  --bg:#f7f8fa; --panel:#fff; --panel-2:#f2f4f7; --line:#e2e6ec;
  --fg:#101419; --dim:#5c6675; --faint:#8d97a8;
  --accent:#0a66c2; --skill:#0a66c2; --rule:#a8620a; --workflow:#7038c8;
  --ok:#127a52; --shadow:0 1px 2px rgba(16,20,25,.06),0 8px 24px rgba(16,20,25,.07);
}}
html,body{margin:0;padding:0}
body{background:var(--bg);color:var(--fg);font-family:var(--sans);
  font-size:14px;line-height:1.55;-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px 64px}
header{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--bg) 88%,transparent);
  backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}
.hd{max-width:1080px;margin:0 auto;padding:14px 20px 0;
  display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.brand{font-family:var(--mono);font-weight:600;font-size:15px;letter-spacing:-.01em}
.brand b{color:var(--accent)}
.stat{color:var(--dim);font-size:12.5px;font-variant-numeric:tabular-nums}
.stat b{color:var(--fg);font-weight:600}
.tabs{max-width:1080px;margin:0 auto;padding:10px 20px 0;display:flex;gap:4px}
.tab{appearance:none;background:none;border:0;border-bottom:2px solid transparent;
  color:var(--dim);font:inherit;font-size:13px;padding:7px 12px 9px;cursor:pointer;
  border-radius:6px 6px 0 0;transition:color .15s,border-color .15s,background .15s}
.tab:hover{color:var(--fg);background:var(--panel-2)}
.tab[aria-selected=true]{color:var(--fg);border-bottom-color:var(--accent);font-weight:600}
.bar{display:flex;gap:10px;align-items:center;margin:20px 0 12px;flex-wrap:wrap}
.search{flex:1 1 320px;position:relative;display:flex;align-items:center}
.search input{width:100%;background:var(--panel);color:var(--fg);
  border:1px solid var(--line);border-radius:var(--r);padding:10px 12px 10px 34px;
  font:inherit;font-size:14px;outline:none;transition:border-color .15s,box-shadow .15s}
.search input:focus{border-color:var(--accent);
  box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 18%,transparent)}
.search svg{position:absolute;left:11px;width:15px;height:15px;stroke:var(--faint);
  fill:none;stroke-width:2;pointer-events:none}
kbd{font-family:var(--mono);font-size:11px;color:var(--faint);border:1px solid var(--line);
  border-bottom-width:2px;border-radius:5px;padding:1px 5px;background:var(--panel-2)}
.rails{display:flex;flex-direction:column;gap:7px;margin-bottom:14px}
.rail{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.rail>.lbl{font-size:11px;text-transform:uppercase;letter-spacing:.07em;
  color:var(--faint);min-width:52px;font-weight:600}
.chip{appearance:none;font:inherit;font-size:12px;cursor:pointer;
  background:var(--panel);color:var(--dim);border:1px solid var(--line);
  border-radius:999px;padding:3px 10px;transition:all .13s;white-space:nowrap}
.chip:hover{color:var(--fg);border-color:var(--faint)}
.chip[aria-pressed=true]{background:color-mix(in srgb,var(--accent) 16%,var(--panel));
  border-color:var(--accent);color:var(--fg);font-weight:600}
.chip .n{color:var(--faint);font-variant-numeric:tabular-nums;margin-left:5px;font-weight:400}
.meta{color:var(--dim);font-size:12.5px;margin:0 0 10px;font-variant-numeric:tabular-nums}
.rows{display:flex;flex-direction:column;gap:1px;background:var(--line);
  border:1px solid var(--line);border-radius:var(--r);overflow:hidden}
.row{background:var(--panel);padding:11px 14px;display:grid;
  grid-template-columns:minmax(0,1fr) auto;gap:3px 14px;align-items:baseline;
  transition:background .12s}
.row:hover{background:var(--panel-2)}
.row .nm{font-family:var(--mono);font-size:13.5px;font-weight:600;
  overflow-wrap:anywhere;display:flex;align-items:center;gap:8px}
.row .desc{grid-column:1;color:var(--dim);font-size:12.5px;overflow-wrap:anywhere}
.row .right{grid-row:1/3;grid-column:2;display:flex;flex-direction:column;
  align-items:flex-end;gap:5px;text-align:right}
.badge{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;
  padding:2px 7px;border-radius:5px;border:1px solid currentColor;line-height:1.5}
.badge.skill{color:var(--skill)} .badge.rule{color:var(--rule)}
.badge.workflow{color:var(--workflow)}
.tap{font-family:var(--mono);font-size:11.5px;color:var(--faint);overflow-wrap:anywhere}
.dot{width:6px;height:6px;border-radius:50%;background:var(--ok);flex:none}
.tagrow{grid-column:1;display:flex;gap:5px;flex-wrap:wrap;margin-top:3px}
.tg{font-size:10.5px;font-family:var(--mono);color:var(--faint);
  background:var(--panel-2);border:1px solid var(--line);border-radius:4px;
  padding:0 5px;cursor:pointer}
.tg:hover{color:var(--fg);border-color:var(--faint)}
.empty{padding:56px 20px;text-align:center;color:var(--dim);background:var(--panel);
  border:1px solid var(--line);border-radius:var(--r)}
.empty b{display:block;color:var(--fg);font-size:15px;margin-bottom:6px}
#graphpane{position:relative;border:1px solid var(--line);border-radius:var(--r);
  background:var(--panel);overflow:hidden;margin-top:16px}
#gcanvas{display:block;width:100%;height:600px;cursor:grab}
#gcanvas:active{cursor:grabbing}
.legend{position:absolute;left:12px;bottom:12px;display:flex;gap:5px;flex-wrap:wrap;
  max-width:calc(100% - 24px)}
.lg{font-size:11px;font-family:var(--mono);padding:2px 7px;border-radius:999px;
  background:color-mix(in srgb,var(--panel) 80%,transparent);border:1px solid var(--line)}
.lg i{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px}
#tip{position:absolute;pointer-events:none;background:var(--panel-2);color:var(--fg);
  border:1px solid var(--line);border-radius:8px;padding:8px 10px;font-size:12px;
  box-shadow:var(--shadow);opacity:0;transition:opacity .12s;max-width:260px;z-index:5}
#tip .t{font-family:var(--mono);font-weight:600;margin-bottom:3px;overflow-wrap:anywhere}
#tip .s{color:var(--dim);font-size:11.5px}
.ghint{position:absolute;right:12px;top:12px;color:var(--faint);font-size:11.5px;
  text-align:right;line-height:1.7}
footer{margin-top:26px;padding-top:14px;border-top:1px solid var(--line);
  color:var(--faint);font-size:12px;display:flex;gap:14px;flex-wrap:wrap}
.hide{display:none!important}
@media (max-width:640px){
  .row{grid-template-columns:minmax(0,1fr)}
  .row .right{grid-row:auto;grid-column:1;flex-direction:row;align-items:center}
  #gcanvas{height:420px}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""


_PAGE_JS = """
var S={q:'',tags:[],rows:[],facets:{},total:0,matched:0,tab:'catalog'};
var GRAPH=null,VIEW={x:0,y:0,k:1},SIM=null,HOVER=null;
var el=function(id){return document.getElementById(id)};
var esc=function(s){var d=document.createElement('div');d.textContent=s==null?'':String(s);
  return d.innerHTML};

function qs(){
  var p=new URLSearchParams();
  if(S.q)p.set('q',S.q);
  S.tags.forEach(function(t){p.append('tag',t)});
  return p.toString();
}
function load(){
  fetch('/search.json?'+qs()).then(function(r){return r.json()}).then(function(d){
    S.rows=d.rows;S.facets=d.facets;S.total=d.total;S.matched=d.matched;
    paintRails();paintRows();
  }).catch(function(){el('rows').innerHTML=
    '<div class="empty"><b>could not reach the server</b>is `boost serve` still running?</div>'});
}
function paintRails(){
  var order=['kind','topic','state','tag','tap'],out=[];
  order.forEach(function(ns){
    var vals=S.facets[ns];if(!vals||!vals.length)return;
    var cap=ns==='tap'?12:ns==='tag'?14:vals.length;
    var chips=vals.slice(0,cap).map(function(kv){
      var tag=ns+':'+kv[0],on=S.tags.indexOf(tag)>=0;
      return '<button class="chip" aria-pressed="'+on+'" data-tag="'+esc(tag)+'">'+
        esc(kv[0])+'<span class="n">'+kv[1]+'</span></button>';
    }).join('');
    var more=vals.length>cap?'<span class="tg">+'+(vals.length-cap)+' more</span>':'';
    out.push('<div class="rail"><span class="lbl">'+ns+'</span>'+chips+more+'</div>');
  });
  el('rails').innerHTML=out.join('');
}
function paintRows(){
  el('meta').textContent=S.matched===S.total
    ? S.total.toLocaleString()+' items'
    : S.matched.toLocaleString()+' of '+S.total.toLocaleString()+' items'+
      (S.rows.length<S.matched?' \\u00b7 showing first '+S.rows.length:'');
  if(!S.rows.length){
    el('rows').innerHTML='<div class="empty"><b>nothing matches</b>'+
      (S.total?'try fewer filters, or a different word':
       'no taps configured yet \\u2014 run <code>boost tap --defaults</code>')+'</div>';
    return;
  }
  el('rows').innerHTML=S.rows.map(function(r){
    var nm=r.kind==='skill'
      ? '<a href="/skill/'+encodeURIComponent(r.name)+'">'+esc(r.name)+'</a>'
      : esc(r.name);
    var tags=r.tags.filter(function(t){return t.indexOf('tap:')!==0}).slice(0,6)
      .map(function(t){return '<span class="tg" data-tag="'+esc(t)+'">'+esc(t)+'</span>'}).join('');
    return '<div class="row"><div class="nm">'+
      (r.installed?'<span class="dot" title="installed"></span>':'')+nm+'</div>'+
      '<div class="desc">'+esc(r.description||'\\u2014')+'</div>'+
      '<div class="tagrow">'+tags+'</div>'+
      '<div class="right"><span class="badge '+esc(r.kind)+'">'+esc(r.kind)+'</span>'+
      '<span class="tap" data-tag="tap:'+esc(r.tap)+'">'+esc(r.tap)+'</span>'+
      '<span class="tap">v'+esc(r.version)+'</span></div></div>';
  }).join('');
}
function toggle(tag){
  var i=S.tags.indexOf(tag);
  if(i>=0)S.tags.splice(i,1);else S.tags.push(tag);
  load();
}
document.addEventListener('click',function(e){
  var t=e.target.closest('[data-tag]');
  if(t){e.preventDefault();toggle(t.getAttribute('data-tag'));return}
  var tb=e.target.closest('.tab');
  if(tb)showTab(tb.dataset.pane);
});
function showTab(name){
  S.tab=name;
  ['catalog','graph'].forEach(function(p){
    el('pane-'+p).classList.toggle('hide',p!==name);
    document.querySelector('.tab[data-pane='+p+']').setAttribute('aria-selected',p===name);
  });
  if(name==='graph')ensureGraph();
}
var qi;
function onInput(v){clearTimeout(qi);qi=setTimeout(function(){S.q=v;load()},110)}
document.addEventListener('keydown',function(e){
  if(e.key==='/'&&document.activeElement!==el('q')){e.preventDefault();el('q').focus()}
  if(e.key==='Escape'&&document.activeElement===el('q')){el('q').value='';onInput('')}
});

/* ---- graph ---- */
var PALETTE=['#6cc2ff','#c08bff','#ffb454','#5fd39b','#ff8fa3','#8fd3ff',
             '#d9c26a','#9aa7ff','#66d9c9','#ff9f6c'];
function ensureGraph(){
  if(GRAPH)return;
  fetch('/graph.json').then(function(r){return r.json()}).then(function(g){
    GRAPH=g;layout(g);draw();paintLegend(g);
  }).catch(function(){});
}
function layout(g){
  var n=g.nodes.length;if(!n)return;
  var byId={};
  g.nodes.forEach(function(d,i){
    var a=i*2.399963,r=18*Math.sqrt(i+1);
    d.x=Math.cos(a)*r;d.y=Math.sin(a)*r;d.vx=0;d.vy=0;
    d.rad=4+Math.sqrt(d.size)*1.7;byId[d.id]=d;
  });
  g.sim=(g.links||[]).map(function(e){return{s:byId[e.source],t:byId[e.target],w:e.weight}})
    .filter(function(l){return l.s&&l.t});
  SIM={alpha:1,g:g};
  step();
}
function step(){
  if(!SIM)return;
  var g=SIM.g,N=g.nodes,a=SIM.alpha;
  for(var i=0;i<N.length;i++){
    var p=N[i];
    for(var j=i+1;j<N.length;j++){
      var q=N[j],dx=q.x-p.x,dy=q.y-p.y,d2=dx*dx+dy*dy||0.01;
      if(d2>90000)continue;
      var f=900/d2,d=Math.sqrt(d2),ux=dx/d*f,uy=dy/d*f;
      p.vx-=ux;p.vy-=uy;q.vx+=ux;q.vy+=uy;
    }
  }
  g.sim.forEach(function(l){
    var dx=l.t.x-l.s.x,dy=l.t.y-l.s.y,d=Math.sqrt(dx*dx+dy*dy)||0.01;
    var f=(d-70)*0.012*Math.min(l.w,4);
    var ux=dx/d*f,uy=dy/d*f;
    l.s.vx+=ux;l.s.vy+=uy;l.t.vx-=ux;l.t.vy-=uy;
  });
  N.forEach(function(p){
    p.vx-=p.x*0.006;p.vy-=p.y*0.006;
    p.x+=p.vx*a;p.y+=p.vy*a;p.vx*=0.82;p.vy*=0.82;
  });
  SIM.alpha*=0.985;
  draw();
  if(SIM.alpha>0.02)requestAnimationFrame(step);
}
function fit(c){
  var g=GRAPH;if(!g||!g.nodes.length)return;
  var xs=g.nodes.map(function(d){return d.x}),ys=g.nodes.map(function(d){return d.y});
  var w=Math.max.apply(null,xs)-Math.min.apply(null,xs)+80;
  var h=Math.max.apply(null,ys)-Math.min.apply(null,ys)+80;
  VIEW.k=Math.min(c.width/Math.max(w,1),c.height/Math.max(h,1),2.2);
}
function draw(){
  var c=el('gcanvas'),g=GRAPH;if(!c||!g)return;
  var dpr=window.devicePixelRatio||1,r=c.getBoundingClientRect();
  if(c.width!==Math.round(r.width*dpr)){c.width=Math.round(r.width*dpr);
    c.height=Math.round(r.height*dpr);fit(c)}
  var x=c.getContext('2d');
  x.setTransform(1,0,0,1,0,0);x.clearRect(0,0,c.width,c.height);
  x.translate(c.width/2+VIEW.x,c.height/2+VIEW.y);x.scale(VIEW.k*dpr,VIEW.k*dpr);
  x.lineCap='round';
  g.sim.forEach(function(l){
    x.strokeStyle='rgba(140,160,190,'+Math.min(0.08+l.w*0.04,0.35)+')';
    x.lineWidth=Math.min(0.5+l.w*0.25,3);
    x.beginPath();x.moveTo(l.s.x,l.s.y);x.lineTo(l.t.x,l.t.y);x.stroke();
  });
  g.nodes.forEach(function(d){
    x.fillStyle=PALETTE[d.community%PALETTE.length];
    x.globalAlpha=HOVER&&HOVER!==d?0.35:1;
    x.beginPath();x.arc(d.x,d.y,d.rad,0,6.2832);x.fill();
    if(d.installed){x.strokeStyle='#5fd39b';x.lineWidth=1.6/VIEW.k;x.stroke()}
    x.globalAlpha=1;
  });
  x.font='500 '+(11/VIEW.k)+'px ui-monospace,monospace';
  x.fillStyle=getComputedStyle(document.body).color;x.textAlign='center';
  g.nodes.forEach(function(d){
    if(d.rad*VIEW.k<7&&HOVER!==d)return;
    x.globalAlpha=HOVER&&HOVER!==d?0.3:0.85;
    x.fillText(d.label,d.x,d.y-d.rad-4/VIEW.k);
  });
  x.globalAlpha=1;
}
function pick(ev){
  var c=el('gcanvas'),r=c.getBoundingClientRect(),dpr=window.devicePixelRatio||1;
  var mx=(ev.clientX-r.left)*dpr,my=(ev.clientY-r.top)*dpr;
  var wx=(mx-c.width/2-VIEW.x)/(VIEW.k*dpr),wy=(my-c.height/2-VIEW.y)/(VIEW.k*dpr);
  var best=null;
  (GRAPH?GRAPH.nodes:[]).forEach(function(d){
    var dx=d.x-wx,dy=d.y-wy;
    if(dx*dx+dy*dy<=(d.rad+3)*(d.rad+3))best=d;
  });
  return best;
}
function paintLegend(g){
  var seen={},out=[];
  g.nodes.forEach(function(d){
    if(seen[d.topic])return;seen[d.topic]=1;
    out.push('<span class="lg"><i style="background:'+
      PALETTE[d.community%PALETTE.length]+'"></i>'+esc(d.topic)+'</span>');
  });
  el('legend').innerHTML=out.slice(0,10).join('');
  var s=g.graph;
  el('gstats').textContent=s.shown+' of '+s.taps+' taps \\u00b7 '+
    s.overlaps+' overlaps'+(s.dropped?' \\u00b7 '+s.dropped+' smallest hidden':'');
}
function wireGraph(){
  var c=el('gcanvas'),drag=null;
  c.addEventListener('mousedown',function(e){drag={x:e.clientX-VIEW.x,y:e.clientY-VIEW.y}});
  window.addEventListener('mouseup',function(){drag=null});
  c.addEventListener('mousemove',function(e){
    if(drag){VIEW.x=e.clientX-drag.x;VIEW.y=e.clientY-drag.y;draw();return}
    var n=pick(e),tip=el('tip');
    if(n!==HOVER){HOVER=n;draw()}
    if(n){
      var r=c.getBoundingClientRect();
      tip.innerHTML='<div class="t">'+esc(n.id)+'</div><div class="s">'+
        n.size+' items \\u00b7 '+esc(n.topic)+
        (n.installed?' \\u00b7 '+n.installed+' installed':'')+'</div>';
      tip.style.opacity=1;
      tip.style.left=Math.min(e.clientX-r.left+14,r.width-250)+'px';
      tip.style.top=(e.clientY-r.top+14)+'px';
    } else tip.style.opacity=0;
  });
  c.addEventListener('mouseleave',function(){el('tip').style.opacity=0;HOVER=null;draw()});
  c.addEventListener('click',function(e){
    var n=pick(e);
    if(n){showTab('catalog');S.tags=['tap:'+n.id];S.q='';el('q').value='';load()}
  });
  c.addEventListener('wheel',function(e){
    e.preventDefault();
    VIEW.k=Math.max(0.15,Math.min(4,VIEW.k*(e.deltaY<0?1.12:0.89)));draw();
  },{passive:false});
  window.addEventListener('resize',function(){if(GRAPH)draw()});
}
el('q').addEventListener('input',function(e){onInput(e.target.value)});
wireGraph();load();
"""


def serve_page() -> str:
    """The catalogue page: a searchable, faceted table and a graph of the taps.

    **No catalog data is interpolated into this markup.** Rows arrive over
    ``fetch`` from the JSON endpoints. Descriptions and names are third-party
    text from whatever repos the reader has tapped, and one containing
    ``</scr`` + ``ipt>`` closes an embedding block and turns the remainder of
    the page into markup it chose — the same class of defect as a 404 that
    echoed its request. Not embedding it removes the class rather than
    escaping around it, and it keeps the shell a constant size no matter how
    large the catalogue gets.
    """
    return (_PAGE_SHELL
            .replace("__CSS__", _PAGE_CSS)
            .replace("__JS__", _PAGE_JS)
            .replace("__VERSION__", html.escape(__version__)))


_PAGE_SHELL = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>boost catalogue</title>
<style>__CSS__</style></head>
<body>
<header>
  <div class="hd">
    <span class="brand">&#9889; <b>boost</b> catalogue</span>
    <span class="stat" id="meta"></span>
  </div>
  <nav class="tabs" role="tablist">
    <button class="tab" role="tab" data-pane="catalog" aria-selected="true">Catalogue</button>
    <button class="tab" role="tab" data-pane="graph" aria-selected="false">Graph</button>
  </nav>
</header>
<div class="wrap">
  <section id="pane-catalog">
    <div class="bar">
      <label class="search">
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/>
          <path d="M20 20l-3.5-3.5"/></svg>
        <input id="q" type="search" autocomplete="off" spellcheck="false"
               placeholder="Search every tapped registry \u2014 name, description, frontmatter">
      </label>
      <span class="stat"><kbd>/</kbd> to search</span>
    </div>
    <div class="rails" id="rails"></div>
    <div class="rows" id="rows"></div>
  </section>
  <section id="pane-graph" class="hide">
    <div id="graphpane">
      <canvas id="gcanvas"></canvas>
      <div class="ghint">drag to pan \u00b7 scroll to zoom<br>click a tap to filter the catalogue</div>
      <div class="legend" id="legend"></div>
      <div id="tip"></div>
    </div>
    <p class="meta" id="gstats"></p>
    <p class="meta">One node per <b>tap</b>, sized by how much it ships and ringed
      when you have something installed from it. An edge is an item name two
      registries both carry \u2014 the structure a table cannot show you.</p>
  </section>
  <footer>
    <span>boost v__VERSION__</span>
    <a href="/catalog.json">catalog.json</a>
    <a href="/installed.json">installed.json</a>
    <a href="/graph.json">graph.json</a>
    <a href="/search.json">search.json</a>
  </footer>
</div>
<script>__JS__</script>
</body></html>"""


def _is_within(base, target) -> bool:
    """True when target resolves inside base (or equals base)."""
    try:
        base_r = base.resolve(strict=False)
        target_r = target.resolve(strict=False)
        target_r.relative_to(base_r)
    except (OSError, ValueError):
        return False
    return True


def _safe_join_within(base, rel):
    """Resolve base/rel and return it only when contained within base."""
    try:
        base_r = base.resolve(strict=False)
        rel_p = rel if hasattr(rel, "is_absolute") else __import__("pathlib").Path(rel)
        if rel_p.is_absolute():
            return None
        candidate = (base_r / rel_p).resolve(strict=False)
        candidate.relative_to(base_r)
    except (OSError, ValueError, TypeError):
        return None
    return candidate


def skill_text(name: str) -> str | None:
    """SKILL.md text for an installed skill, else from a tap. None if unknown."""
    trusted_name = _validated_skill_name(name)
    if trusted_name is None:
        return None
    base = store.skill_store_dir(trusted_name)
    fp = _safe_join_within(base, Path("SKILL.md"))
    if fp is not None and _is_within(base, fp) and fp.is_file():
        return fp.read_text(encoding="utf-8", errors="replace")
    for e in catalog.find(trusted_name):
        try:
            tap_base = registry.get(e["tap"]).path
            rel = Path(e["skill_md"])
            if rel.is_absolute() or ".." in rel.parts:
                continue
            fp = _safe_join_within(tap_base, rel)
        except (BoostError, TypeError, ValueError):
            continue
        if fp is None or not _is_within(tap_base, fp):
            continue
        if fp.is_file():
            return fp.read_text(encoding="utf-8", errors="replace")
    return None


#: The three characters that let a JSON body be read as markup. `json.dumps`
#: leaves them bare, and every one of them is escapable *inside a JSON string*
#: without changing what the document parses to — which is where they can
#: appear at all, since JSON's own structural characters are `{}[],:"` alone.
_JSON_INERT = {"<": "\\u003c", ">": "\\u003e", "&": "\\u0026"}


def _json_body(obj) -> bytes:
    """Serialize, with the markup characters escaped into their \\u form.

    Every JSON body here carries third-party text: a description, a name and a
    tap all come from whatever repos the reader has tapped. Correct
    ``Content-Type`` plus the ``nosniff`` header in :meth:`_CatalogHandler._send`
    is what makes that safe today, and this is the layer that does not depend on
    either being got right — by a proxy, by a future route that types a body
    wrong, or by someone saving the response and opening it. The escapes are
    valid JSON, so ``json.loads`` returns exactly the same object.
    """
    text = json.dumps(obj, indent=2)
    for ch, esc in _JSON_INERT.items():
        text = text.replace(ch, esc)
    return text.encode()


def route(path: str) -> tuple[int, str, bytes]:
    """Map a GET path to ``(status, content_type, body)``. Pure — no socket.

    Mirrors the historical dispatch exactly: ``/`` and ``/index.html`` serve the
    HTML page; ``/catalog.json`` and ``/installed.json`` the JSON views; a
    ``/skill/<name>`` path the raw SKILL.md (404 for an invalid or unknown name);
    anything else a JSON ``not found``.

    Nothing the caller sent comes back out of the invalid-name branch. ``path``
    is unquoted above, so the segment after ``/skill/`` is arbitrary bytes of
    the requester's choosing, and interpolating it into the body made the
    response a reflection of the request. The name is invalid *by definition*
    there, so naming it told the caller nothing it had not just sent — see
    ``_send`` for the nosniff header that is the other half of this.
    """
    raw, _, query = path.partition("?")
    path = urllib.parse.unquote(raw)
    if path in ("/", "/index.html"):
        return 200, "text/html; charset=utf-8", serve_page().encode()
    if path == "/catalog.json":
        return 200, "application/json", _json_body(catalog.all_entries())
    if path == "/installed.json":
        return 200, "application/json", _json_body(lockfile.read())
    if path == "/graph.json":
        return 200, "application/json", _json_body(cached_graph())
    if path == "/search.json":
        params = urllib.parse.parse_qs(query)
        rows, facets = cached_view()
        matched = search_rows(rows, (params.get("q") or [""])[0],
                              params.get("tag") or [])
        return 200, "application/json", _json_body({
            "rows": [public_row(r) for r in matched[:SEARCH_LIMIT]],
            "matched": len(matched),
            "total": len(rows),
            "facets": facets,
        })
    if path.startswith("/skill/"):
        name = path[len("/skill/"):].strip("/")
        if not SKILL_NAME_RE.fullmatch(name):
            return (404, "application/json",
                    _json_body({"error": "invalid skill name"}))
        text = skill_text(name)
        if text is None:
            # Safe to name here, and worth naming: this branch is reachable
            # only for a name that already matched SKILL_NAME_RE, whose charset
            # is [A-Za-z0-9._-] — nothing in it can close a tag or a quote. It
            # is also the message that tells a typo from a not-installed skill.
            return (404, "application/json",
                    _json_body({"error": "no skill named %r" % name}))
        return 200, "text/plain; charset=utf-8", text.encode()
    return 404, "application/json", _json_body({"error": "not found"})


class _CatalogHandler(BaseHTTPRequestHandler):
    server_version = "boost/" + __version__

    # `fmt`, not the base class's `format`: the stdlib only ever calls this
    # positionally, and `format` would shadow the builtin (and read as an
    # unused variable to vulture). The name-mismatch override warning is
    # cosmetic here, so it's suppressed at the line rather than repo-wide.
    def log_message(self, fmt, *args):  # pyright: ignore[reportIncompatibleMethodOverride]
        pass  # request logging happens in _send instead

    def _send(self, status: int, ctype: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # Content sniffing is the only way a body we typed application/json
        # becomes executable markup in a browser. Set here rather than at each
        # return in route(), because this is the one choke point every response
        # passes through — including the generic 500 in do_GET below, which is
        # the response most likely to grow a reflected detail later.
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)
        out.dim("  %s %s → %d" % (self.command, self.path, status))

    def do_GET(self):
        try:
            status, ctype, body = route(self.path)
            self._send(status, ctype, body)
        except BrokenPipeError:
            pass
        except Exception as e:
            # Never leak internal exception detail (filesystem paths, state) to
            # the HTTP client — it reaches remote callers when the server is
            # exposed with `--host 0.0.0.0`. Log the specifics server-side and
            # return a generic body.
            logs.get_logger().warning("serve: %s %s failed: %s: %s",
                                      self.command, self.path,
                                      type(e).__name__, e)
            with contextlib.suppress(Exception):
                self._send(500, "application/json",
                           _json_body({"error": "internal server error"}))


def serve_http(host: str, port: int) -> None:
    """Bind and run the catalog server until interrupted (blocks)."""
    try:
        httpd = ThreadingHTTPServer((host, port), _CatalogHandler)
    except OSError as e:
        # Windows can report a bind against an already-LISTENing port as
        # WinError 10013 (WSAEACCES) rather than EADDRINUSE.
        if e.errno == errno.EADDRINUSE or (
            sys.platform == "win32" and getattr(e, "winerror", None) == 10013
        ):
            raise BoostError("port %d is already in use" % port,
                            hint="pick another with --port") from e
        raise BoostError("cannot bind %s:%d — %s" % (host, port, e),
                        hint="check --host and --port") from e
    out.info("⚡ serving skill catalog on http://%s:%d %s"
             % (host, port, out.c("(ctrl-c to stop)", out.DIM)))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print()
        out.ok("server stopped")
    finally:
        httpd.server_close()

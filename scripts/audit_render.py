"""Objective render audit for kuron-design-figcraft 3.0.0.

Numeric evidence in place of "the PNG looks right": canvas utilization,
text overflow, connector topology, and dot-colour semantics. Each check
cites the SKILL rule ID it enforces.

Pakai: python3 scripts/audit_render.py <file.figcraft> [--screen ID]
Keluar 0 = PASS semua; 1 = ada FAIL (daftar per layar).
"""
import sys, os, json, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figcraft_tool import TOKENS  # noqa: E402

C = TOKENS["colors"]
FAIL = []


def note(screen, rule, msg):
    FAIL.append(f"[{screen}] {rule}: {msg}")


def frame_box(n):
    t = n.get("transform", [1, 0, 0, 1, 0, 0])
    return t[4], t[5], n.get("width", 0), n.get("height", 0)


def audit_screen(nodes, sid):
    s = nodes[str(sid)]
    name = s.get("name", sid)
    sx, sy, sw, sh = frame_box(s)
    if not sw or not sh:
        return
    kids = [nodes[str(c)] for c in s.get("children", []) if str(c) in nodes]
    # §9.1 utilisasi kanvas >= 60% (bounding box isi vs frame).
    xs0, ys0, xs1, ys1 = [], [], [], []
    for k in kids:
        if k.get("type") not in ("frame", "rectangle", "text", "vector"):
            continue
        x, y, w, h = frame_box(k)
        if w > 0 and h > 0:
            xs0.append(x); ys0.append(y); xs1.append(x + w); ys1.append(y + h)
    if xs0:
        area = (max(xs1) - min(xs0)) * (max(ys1) - min(ys0))
        util = area / (sw * sh)
        if util < 0.60:
            note(name, "S-06/§9.1", f"utilisasi kanvas {util:.0%} < 60%")
        # ruang mati bawah > 150px.
        if sy + sh - max(ys1) > 150 and "Flow" not in str(name):
            note(name, "S-06", "ruang mati bawah > 150px")
    # S-08 teks meluber dari ruang induk.
    for k in kids:
        if k.get("type") != "text":
            continue
        p = nodes.get(str(k.get("parent", "")), {})
        pw = p.get("width") or 0
        pad = (p.get("layout") or {}).get("padding", [0, 0, 0, 0]) or [0, 0, 0, 0]
        try:
            inner = float(pw) - float(pad[1]) - float(pad[3])
        except (IndexError, TypeError, ValueError):
            inner = float(pw)
        if pw and k.get("width", 0) > inner + 1:
            note(name, "S-08", f"teks '{k.get('name')}' meluber "
                 f"({k.get('width', 0):.0f} > {inner:.0f})")
    # S-03 topologi: vector konektor harus beranchor di dua node.
    for k in kids:
        if k.get("type") != "vector" or not str(k.get("name", "")).startswith(
                ("lnk", "drop", "back", "br", "loop", "blink")):
            continue
        net = k.get("network", {})
        vs = net.get("vertices", [])
        if not vs:
            note(name, "S-03", f"konektor '{k.get('name')}' tanpa vertices")
            continue
        pts = [(v["x"], v["y"]) for v in vs]
        anchored = 0
        for (px, py) in (pts[0], pts[-1]):
            for m in kids:
                if m.get("type") not in ("frame", "rectangle"):
                    continue
                x, y, w, h = frame_box(m)
                if x - 4 <= px <= x + w + 4 and y - 4 <= py <= y + h + 4:
                    anchored += 1
                    break
        if anchored < 2:
            note(name, "S-03", f"konektor '{k.get('name')}' yatim "
                 f"({anchored}/2 ujung menempel)")
    # §9.4 semantik dot: SELESAI->success, BATAL->muted, PRASYARAT->warn.
    def subtree(nid):
        out = []
        stack = [str(nid)]
        while stack:
            cur = nodes.get(stack.pop(), {})
            out.append(cur)
            stack.extend(str(c) for c in cur.get("children", []))
        return out

    for k in kids:
        nm = str(k.get("name", ""))
        if k.get("type") != "frame" or not (
                nm.startswith("Note_") or nm == "Prereq"):
            continue
        desc = subtree(k.get("id"))
        titles = " ".join(str(t.get("characters", "")) for t in desc
                          if t.get("type") == "text").upper()
        dots = [d for d in desc if d.get("type") == "rectangle"
                and (d.get("width") or 0) <= 12]
        for d in dots:
            fills = d.get("fills", []) or []
            if not fills or not isinstance(fills[0].get("color"), dict):
                continue
            from figcraft_tool import _lint_hex as _hx
            h = _hx(fills[0]["color"])
            want = None
            if "BATAL" in titles:
                want = C["ink_muted"].lower()
            elif "SELESAI" in titles or "NOTIFIKASI" in titles:
                want = C["success"].lower()
            elif "PRASYARAT" in titles or "IZIN" in titles:
                want = C["warning"].lower()
            if want and h != want:
                note(name, "§9.4", f"dot '{nm}' {h} tak sesuai semantik "
                     f"(harusnya {want})")


def audit_file(path, screen_id=None):
    with zipfile.ZipFile(path) as z:
        doc = json.load(z.open("document.json"))
    nodes = doc.get("nodes", {})
    if screen_id:
        audit_screen(nodes, screen_id)
    else:
        for pid in doc.get("pages", [1]):
            page = nodes.get(str(pid), {})
            for cid in page.get("children", []):
                c = nodes.get(str(cid), {})
                if c.get("type") in ("frame",) and (c.get("width") or 0) >= 1000:
                    audit_screen(nodes, cid)
    return FAIL


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("pakai: audit_render.py <file.figcraft> [--screen ID]")
        sys.exit(2)
    sid = None
    if "--screen" in sys.argv:
        sid = sys.argv[sys.argv.index("--screen") + 1]
    fails = audit_file(sys.argv[1], sid)
    if fails:
        print("FAIL:")
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print("PASS: semua layar lolos audit render.")

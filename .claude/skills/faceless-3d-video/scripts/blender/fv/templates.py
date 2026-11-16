"""Scene templates. Each template is `fn(ctx, p)` where `p` is the beat's `scene` dict.
Register new ones with @template("name", "alias", ...). See reference/scene-templates.md.
"""
import math

import bpy
from mathutils import Matrix, Vector

from .core import (_try, ambient_shapes, area_light, camera, dims, ease, empty, floor, hex_rgba,
                   hud, hud_top, key, key_idx, light_rig, mat_emission, mat_preset,
                   mat_principled, mat_text, pop_in, prim, show_between, slide_in, spin,
                   starfield, text, wobble, word_block, world_gradient)

TEMPLATES = {}
DOCS = {}


def template(*names):
    def deco(fn):
        for n in names:
            TEMPLATES[n] = fn
        DOCS[names[0]] = (fn.__doc__ or "").strip()
        return fn
    return deco


def color_of(ctx, p, default="primary"):
    c = p.get("color", default)
    return ctx.style.get(c, c) if not str(c).startswith("#") else c


def background(ctx, p, default="shapes"):
    world_gradient(ctx)
    bg = p.get("background", default)
    if bg in ("shapes", "both"):
        ambient_shapes(ctx, count=int(p.get("shape_count", 12)))
    if bg in ("stars", "both"):
        starfield(ctx, count=int(p.get("star_count", 600)), radius=45)


def fmt_num(v, decimals=0, sep=True):
    s = f"{v:,.{decimals}f}" if sep else f"{v:.{decimals}f}"
    return s


# =========================================================================== text
@template("title", "title_card", "kinetic_text", "hook", "statement")
def t_title(ctx, p):
    """Kinetic 3D typography. params: text (wrap words in *stars* to highlight),
    subtitle, size (1.0), anim (pop|slide|drop|none), stagger (frames, 3),
    camera (push), background (shapes|stars|both|none)."""
    background(ctx, p)
    light_rig(ctx, (0, 0, ctx.cz))
    cam, _ = camera(ctx, p.get("camera", "push"), target=(0, 0, ctx.cz))
    sub = p.get("subtitle")
    size = ctx.u * 1.15 * float(p.get("size", 1.0))
    body_h = ctx.ch * (0.72 if sub else 0.92)
    words, h = word_block(ctx, p.get("text", "Untitled"), size, ctx.cw,
                          center=(0, 0, ctx.cz + (ctx.ch * 0.1 if sub else 0)),
                          start_frame=ctx.f(0.02), stagger=int(p.get("stagger", 3)),
                          anim=p.get("anim", "pop"), max_h=body_h)
    for w in words:
        wobble(w, "location", strength=0.03, scale=50, indices=(2,))
    if sub:
        f = ctx.f(0.02) + len(words) * int(p.get("stagger", 3)) + 4
        word_block(ctx, sub, ctx.u * 0.42, ctx.cw * 0.9,
                   center=(0, -0.3, ctx.cz + ctx.ch * 0.1 - h / 2 - ctx.u * 0.75),
                   start_frame=f, stagger=1, anim="slide", base_mat=mat_text(ctx, "secondary"),
                   max_h=ctx.ch * 0.25)


@template("quote")
def t_quote(ctx, p):
    """Big pull-quote. params: text, author."""
    background(ctx, p, "shapes")
    light_rig(ctx, (0, 0, ctx.cz))
    camera(ctx, p.get("camera", "drift"), target=(0, 0, ctx.cz))
    qm = text(ctx, "“", size=ctx.u * 3.2, mat=mat_preset(ctx, "neon" if ctx.dark else "glossy",
                                                              ctx.style["accent"]),
              loc=(-ctx.cw * 0.36, 0.4, ctx.cz + ctx.ch * 0.36))
    pop_in(qm, ctx.f(0.0), dur=14)
    spin(qm, ctx.frames, turns=0.03, axis=1)
    words, h = word_block(ctx, p.get("text", ""), ctx.u * 0.62, ctx.cw * 0.92,
                          center=(0, 0, ctx.cz), start_frame=ctx.f(0.04), stagger=2,
                          anim="slide", max_h=ctx.ch * 0.7)
    if p.get("author"):
        a = text(ctx, "— " + p["author"], size=ctx.u * 0.38, mat=mat_text(ctx, "secondary"),
                 loc=(0, 0, ctx.cz - h / 2 - ctx.u * 0.6), max_w=ctx.cw)
        pop_in(a, ctx.f(0.45))


@template("cta", "outro", "subscribe")
def t_cta(ctx, p):
    """Call-to-action outro. params: text ('Follow for more'), subtitle."""
    background(ctx, p, "both")
    light_rig(ctx, (0, 0, ctx.cz))
    camera(ctx, p.get("camera", "push"), target=(0, 0, ctx.cz))
    R = min(ctx.cw * 0.5, ctx.ch * 0.6)
    ring = prim("ring", size=R, loc=(0, 1.5, ctx.cz),
                mat=mat_preset(ctx, "neon", ctx.style["primary"]), rot=(math.pi / 2, 0, 0))
    pop_in(ring, 1, dur=16)
    spin(ring, ctx.frames, turns=0.5, axis=1)
    ring2 = prim("ring", size=R * 0.88, loc=(0, 1.6, ctx.cz),
                 mat=mat_preset(ctx, "neon", ctx.style["secondary"]), rot=(math.pi / 2 + 0.35, 0, 0))
    pop_in(ring2, 4, dur=16)
    spin(ring2, ctx.frames, turns=-0.5, axis=1)
    wobble(ring2, "rotation_euler", strength=0.15, scale=50, indices=(0,))
    words, h = word_block(ctx, p.get("text", "Follow for *more*"), ctx.u * 0.9, min(ctx.cw * 0.62, R * 1.3),
                          center=(0, -0.5, ctx.cz + ctx.u * 0.3), start_frame=ctx.f(0.05),
                          stagger=3, anim="drop", max_h=ctx.ch * 0.5)
    arrow = prim("cone", size=ctx.u * 0.35, loc=(0, 0, ctx.cz - h / 2 - ctx.u * 0.9),
                 mat=mat_preset(ctx, "glossy", ctx.style["accent"]), rot=(math.pi, 0, 0))
    pop_in(arrow, ctx.f(0.25))
    z0 = arrow.location.z
    for i, fr in enumerate(range(ctx.f(0.3), ctx.frames, max(6, ctx.fps // 2))):
        key_idx(arrow, "location", 2, fr, z0 - (ctx.u * 0.25 if i % 2 else 0), "inout")
    if p.get("subtitle"):
        s = text(ctx, p["subtitle"], size=ctx.u * 0.4, mat=mat_text(ctx, "secondary"),
                 loc=(0, 0, z0 - ctx.u * 0.9), max_w=ctx.cw)
        pop_in(s, ctx.f(0.35))


# =========================================================================== objects
@template("hero", "hero_object", "object", "product")
def t_hero(ctx, p):
    """A single hero object on a reflective floor with an orbiting camera.
    params: object (sphere|cube|torus|cone|cylinder|icosphere|monkey|gem|crystal|ring|coin|
    capsule|pyramid), material (glossy|metal|gold|chrome|glass|neon|clay), color,
    label (top title), caption (small text under object), camera (orbit)."""
    world_gradient(ctx)
    bg = p.get("background", "shapes")
    if bg in ("stars", "both"):
        starfield(ctx, 500, 45)
    s = min(ctx.cw, ctx.ch) * 0.26 * float(p.get("size", 1.0))
    c = Vector((0, 0, ctx.cz - (ctx.u * 0.2 if p.get("label") else 0)))
    o = prim(p.get("object", "sphere"), size=s, loc=c,
             mat=mat_preset(ctx, p.get("material", "glossy"), color_of(ctx, p)))
    pop_in(o, 1, dur=14)
    spin(o, ctx.frames, turns=float(p.get("turns", 0.35)), axis=2)
    wobble(o, "location", strength=s * 0.06, scale=45, indices=(2,))
    if bg in ("shapes", "both"):
        ambient_shapes(ctx, count=8, depth=(5, 14))
    floor(ctx, z=c.z - s * 1.55)
    if p.get("pedestal", False):
        ped = prim("cylinder", size=s * 0.9, loc=(0, 0, c.z - s * 1.55 + s * 0.15),
                   mat=mat_preset(ctx, "matte", ctx.style["floor"]))
        ped.scale = (1.3, 1.3, 0.12)
    light_rig(ctx, c)
    cam, _ = camera(ctx, p.get("camera", "orbit"), target=c, height=s * 0.9,
                    orbit_deg=float(p.get("orbit", 50)))
    if p.get("label"):
        hud(ctx, cam, p["label"], hud_top(ctx), ctx.u * 0.75, start=ctx.f(0.06))
    if p.get("caption"):
        hud(ctx, cam, p["caption"], hud_top(ctx) - ctx.u * 0.85, ctx.u * 0.38,
            color="secondary", start=ctx.f(0.12))


@template("versus", "comparison", "vs")
def t_versus(ctx, p):
    """Two objects head-to-head. params: left/right: {label, object, material, color, value}.
    If both have numeric 'value', object sizes are scaled to compare."""
    world_gradient(ctx)
    L, R = p.get("left", {}), p.get("right", {})
    vals = [float(x.get("value", 1) or 1) for x in (L, R)]
    m = max(vals)
    s0 = min(ctx.cw * 0.2, ctx.ch * 0.22)
    zc = ctx.cz
    fl_z = zc - s0 * 1.6
    floor(ctx, z=fl_z)
    light_rig(ctx, (0, 0, zc))
    cam, _ = camera(ctx, p.get("camera", "push"), target=(0, 0, zc), height=s0 * 0.6)
    for i, (side, v, col) in enumerate(((L, vals[0], "primary"), (R, vals[1], "secondary"))):
        x = (-1 if i == 0 else 1) * ctx.cw * 0.26
        s = s0 * (0.45 + 0.55 * math.sqrt(v / m)) if ("value" in L and "value" in R) else s0
        o = prim(side.get("object", "sphere"), size=s, loc=(x, 0, fl_z + s * 1.15),
                 mat=mat_preset(ctx, side.get("material", "glossy"), side.get("color", ctx.style[col])))
        f = ctx.f(0.03 + i * 0.12)
        pop_in(o, f, dur=14)
        spin(o, ctx.frames, turns=0.25 * (1 if i else -1))
        lbl = side.get("label", "A" if i == 0 else "B")
        if "value" in side and p.get("show_values", True):
            lbl = f"{lbl}\n{side.get('prefix', '')}{fmt_num(v, int(side.get('decimals', 0)))}{side.get('suffix', '')}"
        t = text(ctx, lbl, size=ctx.u * 0.42, loc=(x, -s0, fl_z + 2 * s + s0 * 0.75),
                 max_w=ctx.cw * 0.44)
        pop_in(t, f + 6)
    vs = text(ctx, p.get("vs_text", "VS"), size=ctx.u * 0.9,
              mat=mat_preset(ctx, "neon" if ctx.dark else "glossy", ctx.style["accent"]),
              loc=(0, -s0 * 0.5, fl_z + s0 * 1.2))
    pop_in(vs, ctx.f(0.3), dur=12)
    if p.get("title"):
        hud(ctx, cam, p["title"], hud_top(ctx), ctx.u * 0.6, start=ctx.f(0.02))


@template("image_card", "image", "photo")
def t_image(ctx, p):
    """Floating 3D card showing an image (stock photo, AI art, screenshot, diagram).
    params: image (path), images (list of up to 3 paths for a fanned stack), caption."""
    background(ctx, p, "shapes")
    light_rig(ctx, (0, 0, ctx.cz))
    cam, _ = camera(ctx, p.get("camera", "push"), target=(0, 0, ctx.cz))
    paths = p.get("images") or ([p["image"]] if p.get("image") else [])
    if not paths:
        paths = [None]
    n = len(paths)
    for i, path in enumerate(paths[:3]):
        img = _try(bpy.data.images.load, path) if path else None
        aspect = (img.size[0] / img.size[1]) if img and img.size[1] else 16 / 9
        w = min(ctx.cw * (0.95 if n == 1 else 0.75), ctx.ch * 0.8 * aspect)
        h = w / aspect
        bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
        card = bpy.context.view_layer.objects.active
        card.scale = (w, h, 1)
        bpy.ops.object.transform_apply(scale=True)
        card.rotation_euler = (math.pi / 2, 0, 0)
        off = (i - (n - 1) / 2)
        card.location = (off * w * 0.18, -i * 0.15, ctx.cz + off * h * 0.06)
        card.rotation_euler[1] = math.radians(-off * 6)
        sol = card.modifiers.new("solid", "SOLIDIFY")
        sol.thickness = 0.06
        m = bpy.data.materials.new("img")
        nt = m.node_tree
        b = [n_ for n_ in nt.nodes if n_.type == "BSDF_PRINCIPLED"][0]
        if img:
            tx = nt.nodes.new("ShaderNodeTexImage")
            tx.image = img
            nt.links.new(tx.outputs["Color"], b.inputs["Base Color"])
            if b.inputs.get("Emission Color"):
                nt.links.new(tx.outputs["Color"], b.inputs["Emission Color"])
                b.inputs["Emission Strength"].default_value = 0.6
        else:
            b.inputs["Base Color"].default_value = hex_rgba(ctx.style["secondary"])
        b.inputs["Roughness"].default_value = 0.35
        card.data.materials.append(m)
        f = ctx.f(0.02 + i * 0.08)
        slide_in(card, f, offset=(0, 0, -ctx.vh * 0.6), dur=16)
        wobble(card, "rotation_euler", strength=0.04, scale=70, indices=(0, 1))
    if p.get("caption"):
        hud(ctx, cam, p["caption"], hud_top(ctx), ctx.u * 0.55, start=ctx.f(0.1))


# =========================================================================== data
@template("bar_chart", "bars", "chart")
def t_bars(ctx, p):
    """Growing 3D bar chart. params: bars [{label, value, color?}] (2-8), title,
    prefix, suffix, decimals."""
    world_gradient(ctx)
    bars = p.get("bars") or [{"label": "A", "value": 3}, {"label": "B", "value": 5}]
    n = len(bars)
    mx = max(float(b["value"]) for b in bars) or 1
    W = ctx.cw * 0.95
    sp = W / n
    bw = sp * 0.62
    has_title = bool(p.get("title"))
    Hmax = ctx.ch * (0.5 if has_title else 0.6)
    base = ctx.cz - ctx.ch * 0.42
    floor(ctx, z=base)
    light_rig(ctx, (0, 0, ctx.cz))
    cam, _ = camera(ctx, p.get("camera", "orbit"), target=(0, 0, base + Hmax * 0.55),
                    height=ctx.u * 1.4, orbit_deg=float(p.get("orbit", 18)))
    cols = [ctx.style["primary"], ctx.style["secondary"], ctx.style["accent"]]
    grow0, grow1 = 0.05, float(p.get("grow_until", 0.55))
    for i, b in enumerate(bars):
        x = -W / 2 + sp * (i + 0.5)
        h = max(0.02, Hmax * float(b["value"]) / mx)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
        bar = bpy.context.view_layer.objects.active
        bar.data.transform(Matrix.Translation((0, 0, 0.5)))
        bar.scale = (bw, bw * 0.6, 1)
        bpy.ops.object.transform_apply(scale=True)
        bar.location = (x, 0, base)
        bm = bar.modifiers.new("bevel", "BEVEL")
        bm.width, bm.segments = min(bw, 0.2) * 0.12, 3
        bar.data.materials.append(mat_preset(ctx, p.get("material", "glossy"),
                                             b.get("color", cols[i % len(cols)])))
        f0 = ctx.f(grow0 + (grow1 - grow0) * i / max(1, n))
        f1 = f0 + max(8, int(ctx.fps * 0.7))
        key(bar, "scale", 1, (1, 1, 0.001), "const")
        key(bar, "scale", f0, (1, 1, 0.001), "back")
        key(bar, "scale", f1, (1, 1, h), "inout")
        val = f"{p.get('prefix', '')}{fmt_num(float(b['value']), int(p.get('decimals', 0)))}{p.get('suffix', '')}"
        vt = text(ctx, val, size=ctx.u * 0.36, loc=(x, 0, base + h + ctx.u * 0.3), max_w=sp * 0.95)
        pop_in(vt, f1 - 2)
        if b.get("label"):
            lt = text(ctx, b["label"], size=ctx.u * 0.28, mat=mat_text(ctx, "secondary"),
                      loc=(x, 0, base + h + ctx.u * 0.72), max_w=sp * 0.95, extrude=0.01)
            pop_in(lt, f1)
    if has_title:
        hud(ctx, cam, p["title"], hud_top(ctx), ctx.u * 0.6, start=ctx.f(0.0))


@template("counter", "number", "stat", "big_number")
def t_counter(ctx, p):
    """Big number counting up. params: to, from (0), decimals (0), prefix, suffix,
    label (text under the number), count_until (0.6 = fraction of beat)."""
    background(ctx, p, "stars" if ctx.dark else "shapes")
    light_rig(ctx, (0, 0, ctx.cz))
    camera(ctx, p.get("camera", "push"), target=(0, 0, ctx.cz))
    a, b = float(p.get("from", 0)), float(p.get("to", 100))
    dec = int(p.get("decimals", 0))
    pre, suf = p.get("prefix", ""), p.get("suffix", "")
    f0, f1 = ctx.f(0.03), ctx.f(float(p.get("count_until", 0.6)))
    steps = max(1, min(48, f1 - f0))
    size = ctx.u * 1.7
    zc = ctx.cz + (ctx.u * 0.35 if p.get("label") else 0)
    mat = mat_preset(ctx, "neon" if ctx.dark else "glossy", ctx.style["primary"]) \
        if p.get("glow", ctx.dark) else mat_text(ctx)
    final_body = f"{pre}{fmt_num(b, dec)}{suf}"
    probe = text(ctx, final_body, size=size, mat=mat, max_w=ctx.cw * 0.95, max_h=ctx.ch * 0.5)
    sc = probe.scale[0]
    num_w = dims(probe).x
    bpy.data.objects.remove(probe)
    prev_body, prev_obj, prev_f = None, None, f0
    for s in range(steps + 1):
        fr = f0 + int(round((f1 - f0) * s / steps))
        v = a + (b - a) * ease(s / steps, "out")
        body = f"{pre}{fmt_num(v, dec)}{suf}" if s < steps else final_body
        if body == prev_body:
            continue
        o = text(ctx, body, size=size, mat=mat, loc=(0, 0, zc))
        o.scale = (sc, sc, sc)
        if prev_obj is not None:
            show_between(prev_obj, prev_f, fr)
        prev_body, prev_obj, prev_f = body, o, fr
    show_between(prev_obj, prev_f, None)
    pop_in(prev_obj, f1, dur=10, from_scale=0.85)
    r = min(max(min(ctx.cw, ctx.ch) * 0.48, num_w * 0.58), ctx.vw * 0.5)
    ring = prim("ring", size=r, loc=(0, 2.0, zc), rot=(math.pi / 2, 0, 0),
                mat=mat_preset(ctx, "neon" if ctx.dark else "glossy", ctx.style["secondary"]))
    pop_in(ring, 1, dur=18)
    spin(ring, ctx.frames, turns=0.4, axis=1)
    # celebratory burst when the count lands
    for i in range(18):
        ang = 2 * math.pi * i / 18
        d = prim("icosphere", size=ctx.u * 0.07, loc=(0, 0.5, zc),
                 mat=mat_preset(ctx, "neon" if ctx.dark else "glossy", ctx.style["accent"]))
        key(d, "scale", 1, (0, 0, 0), "const")
        key(d, "scale", f1, (1, 1, 1), "out")
        key(d, "location", f1, (0, 0.5, zc), "out")
        key(d, "location", f1 + 18, (math.cos(ang) * r * 1.3, 0.5, zc + math.sin(ang) * r * 1.3), "inout")
        key(d, "scale", f1 + 14, (1, 1, 1), "in")
        key(d, "scale", f1 + 24, (0, 0, 0), "const")
    if p.get("label"):
        lt = text(ctx, p["label"], size=ctx.u * 0.45, mat=mat_text(ctx, "text"),
                  loc=(0, 0, zc - size * sc * 0.75 - ctx.u * 0.35), max_w=ctx.cw)
        pop_in(lt, ctx.f(0.1))


@template("list", "list_reveal", "steps", "top_list")
def t_list(ctx, p):
    """Numbered list revealed item by item. params: items [str] (2-6), title,
    reveal_at [fractions of beat] (default evenly spread), numbered (true)."""
    world_gradient(ctx)
    if p.get("background", "shapes") != "none":
        ambient_shapes(ctx, count=8, depth=(8, 18))
    items = p.get("items") or ["First", "Second", "Third"]
    n = len(items)
    has_title = bool(p.get("title"))
    top = ctx.cz + ctx.ch / 2 - (ctx.u * 0.9 if has_title else 0)
    avail = ctx.ch - (ctx.u * 0.9 if has_title else 0)
    rh = min(avail / n, ctx.u * 1.35)
    light_rig(ctx, (0, 0, ctx.cz))
    cam, _ = camera(ctx, p.get("camera", "push"), target=(0, 0, ctx.cz))
    if has_title:
        t = text(ctx, p["title"], size=ctx.u * 0.62, loc=(0, 0, top + ctx.u * 0.45), max_w=ctx.cw)
        pop_in(t, 1)
    reveal = p.get("reveal_at") or [0.04 + 0.7 * i / max(1, n) for i in range(n)]
    slab_mat = mat_principled("slab", ctx.style["floor"] if ctx.dark else "#FFFFFF", rough=0.3, coat=0.5)
    cols = [ctx.style["primary"], ctx.style["secondary"], ctx.style["accent"]]
    for i, it in enumerate(items):
        z = top - rh * (i + 0.5)
        f = ctx.f(float(reveal[min(i, len(reveal) - 1)]))
        grp = empty(f"row{i}", (0, 0, z))
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.25, 0))
        slab = bpy.context.view_layer.objects.active
        slab.scale = (ctx.cw, 0.25, rh * 0.82)
        bpy.ops.object.transform_apply(scale=True)
        bv = slab.modifiers.new("bevel", "BEVEL")
        bv.width, bv.segments = rh * 0.2, 5
        slab.data.materials.append(slab_mat)
        slab.parent = grp
        bx = -ctx.cw / 2 + rh * 0.55
        badge = prim("coin", size=rh * 0.32, loc=(bx, -0.05, 0),
                     mat=mat_preset(ctx, "glossy", cols[i % 3]))
        badge.parent = grp
        if p.get("numbered", True):
            num = text(ctx, str(i + 1), size=rh * 0.42, loc=(bx, -0.25, 0),
                       mat=mat_principled("num", "#FFFFFF" if ctx.dark else ctx.style["text"], emit=0.5 if ctx.dark else 0))
            num.parent = grp
        tx = text(ctx, it, size=rh * 0.36, align="LEFT", loc=(bx + rh * 0.55, -0.15, 0),
                  max_w=ctx.cw - rh * 1.4, max_h=rh * 0.75)
        tx.parent = grp
        slide_in(grp, f, offset=(ctx.vw, 0, 0), dur=14)
        wobble(grp, "rotation_euler", strength=0.015, scale=60, indices=(0, 2))


@template("timeline")
def t_timeline(ctx, p):
    """Events along a line (horizontal in landscape, vertical in shorts).
    params: events [{label, sub}] (2-6), title."""
    world_gradient(ctx)
    if p.get("background", "shapes") != "none":
        ambient_shapes(ctx, count=8, depth=(8, 18))
    ev = p.get("events") or [{"label": "1900"}, {"label": "2000"}]
    n = len(ev)
    light_rig(ctx, (0, 0, ctx.cz))
    cam, _ = camera(ctx, p.get("camera", "push"), target=(0, 0, ctx.cz))
    lm = mat_preset(ctx, "neon" if ctx.dark else "glossy", ctx.style["primary"])
    has_title = bool(p.get("title"))
    if has_title:
        hud(ctx, cam, p["title"], hud_top(ctx), ctx.u * 0.6)
    vertical = ctx.portrait
    L = (ctx.ch * (0.82 if has_title else 0.95)) if vertical else ctx.cw * 0.92
    line = prim("cylinder", size=1, loc=(0, 0, 0), mat=lm)
    line.scale = (ctx.u * 0.03, ctx.u * 0.03, L / 1.8)
    if vertical:
        line.location = (-ctx.cw * 0.32, 0, ctx.cz - (ctx.u * 0.3 if has_title else 0))
    else:
        line.location = (0, 0, ctx.cz)
        line.rotation_euler = (0, math.pi / 2, 0)
    key(line, "scale", 1, (line.scale[0], line.scale[1], 0), "out")
    key(line, "scale", ctx.f(0.25), (line.scale[0], line.scale[1], L / 1.8), "inout")
    reveal = p.get("reveal_at") or [0.08 + 0.65 * i / max(1, n) for i in range(n)]
    cols = [ctx.style["primary"], ctx.style["secondary"], ctx.style["accent"]]
    for i, e in enumerate(ev):
        t = (i + 0.5) / n
        f = ctx.f(float(reveal[min(i, len(reveal) - 1)]))
        if vertical:
            pos = Vector((line.location.x, 0, line.location.z + L / 2 - t * L))
        else:
            pos = Vector((-L / 2 + t * L, 0, ctx.cz))
        dot = prim("sphere", size=ctx.u * 0.16, loc=pos,
                   mat=mat_preset(ctx, "neon" if ctx.dark else "glossy", cols[i % 3]))
        pop_in(dot, f)
        if vertical:
            lt = text(ctx, e.get("label", ""), size=ctx.u * 0.5, align="LEFT",
                      loc=(pos.x + ctx.u * 0.45, -0.1, pos.z + (ctx.u * 0.18 if e.get("sub") else 0)),
                      max_w=ctx.cw * 0.75)
            pop_in(lt, f + 2)
            if e.get("sub"):
                st = text(ctx, e["sub"], size=ctx.u * 0.3, align="LEFT", mat=mat_text(ctx, "secondary"),
                          loc=(pos.x + ctx.u * 0.45, -0.1, pos.z - ctx.u * 0.32), max_w=ctx.cw * 0.75,
                          extrude=0.01)
                pop_in(st, f + 4)
        else:
            up = 1 if i % 2 == 0 else -1
            sp = L / n * 0.95
            lt = text(ctx, e.get("label", ""), size=ctx.u * 0.45,
                      loc=(pos.x, -0.1, pos.z + up * ctx.u * 0.65), max_w=sp)
            pop_in(lt, f + 2)
            if e.get("sub"):
                st = text(ctx, e["sub"], size=ctx.u * 0.26, mat=mat_text(ctx, "secondary"),
                          loc=(pos.x, -0.1, pos.z + up * ctx.u * 1.15), max_w=sp, extrude=0.01)
                pop_in(st, f + 4)


# =========================================================================== worlds
PLANETS = {
    "earth": ["#0B3D91", "#1B6FB5", "#3E8E41", "#8C7A4F", "#F2F2F2"],
    "mars": ["#5B1E0F", "#8E3B1F", "#B5562C", "#D98B5F", "#E8C7A9"],
    "ice": ["#16324F", "#3E7CB1", "#9BC4E2", "#DCEBF5", "#FFFFFF"],
    "lava": ["#120202", "#2A0A05", "#5C1408", "#FF4500", "#FFC93C"],
    "gas": ["#6B4226", "#A0703C", "#D9B38C", "#F2E3C9", "#B5651D"],
    "alien": ["#1A0B2E", "#4B1D6B", "#00A896", "#7BE0AD", "#F9F871"],
    "moon": ["#2B2B2B", "#4A4A4A", "#6E6E6E", "#9A9A9A", "#C8C8C8"],
}


@template("globe", "planet", "world")
def t_globe(ctx, p):
    """Procedural planet with atmosphere, optional rings, in a starfield.
    params: planet (earth|mars|ice|lava|gas|alien|moon), rings (bool), label, caption."""
    world_gradient(ctx, ambient=0.08 if ctx.dark else 0.5)
    starfield(ctx, count=int(p.get("star_count", 900)), radius=50)
    kind = p.get("planet", "earth")
    pal = PLANETS.get(kind, PLANETS["earth"])
    r = min(ctx.cw, ctx.ch) * 0.36 * float(p.get("size", 1.0))
    c = (0, 0, ctx.cz - (ctx.u * 0.25 if p.get("label") else 0))
    pl = prim("sphere", size=r, loc=c)
    m = bpy.data.materials.new("planet")
    nt = m.node_tree
    b = [n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"][0]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    if kind == "gas":
        tex = nt.nodes.new("ShaderNodeTexWave")
        tex.wave_type = "BANDS"
        _try(setattr, tex, "bands_direction", "Z")
        tex.inputs["Scale"].default_value = 2.5
        tex.inputs["Distortion"].default_value = 6
    else:
        tex = nt.nodes.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = 2.2
        tex.inputs["Detail"].default_value = 10
    nt.links.new(tc.outputs["Object"], tex.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.35, hex_rgba(pal[0])
    els[1].position, els[1].color = 0.75, hex_rgba(pal[4])
    for pos, col in ((0.48, pal[1]), (0.53, pal[2]), (0.65, pal[3])):
        e = els.new(pos)
        e.color = hex_rgba(col)
    nt.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = 0.6
    if kind == "lava":
        nt.links.new(ramp.outputs["Color"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = 1.5
    pl.data.materials.append(m)
    pl.rotation_euler = (math.radians(15), 0, 0)
    spin(pl, ctx.frames, turns=float(p.get("turns", 0.12)), axis=2)
    pop_in(pl, 1, dur=18, kind="out", from_scale=0.6)
    # atmosphere shell: fresnel-weighted emission over transparency
    atm = prim("sphere", size=r * 1.035, loc=c)
    am = bpy.data.materials.new("atmo")
    nt = am.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.35
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = hex_rgba(p.get("atmosphere", "#6FB7FF" if kind != "mars" else "#FF9966"))
    em.inputs["Strength"].default_value = 2.5
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mx = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lw.outputs["Facing"], mx.inputs["Fac"])
    nt.links.new(tr.outputs[0], mx.inputs[1])
    nt.links.new(em.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs["Surface"])
    _try(setattr, am, "surface_render_method", "BLENDED")
    atm.data.materials.append(am)
    _try(setattr, atm, "visible_shadow", False)
    pop_in(atm, 1, dur=18, kind="out", from_scale=0.6)
    if p.get("rings", kind == "gas"):
        rg = prim("torus", size=r * 1.7, loc=c, rot=(math.radians(75), math.radians(10), 0),
                  mat=mat_principled("rings", pal[3], rough=0.5, alpha=0.85))
        rg.scale = (1, 1, 0.04)
        pop_in(rg, 6, dur=18)
    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = float(p.get("sun", 4.0))
    so = bpy.data.objects.new("sun", sun)
    bpy.context.scene.collection.objects.link(so)
    so.rotation_euler = (math.radians(60), math.radians(-35), math.radians(-30))
    cam, _ = camera(ctx, p.get("camera", "push"), target=c)
    if p.get("label"):
        hud(ctx, cam, p["label"], hud_top(ctx), ctx.u * 0.75, start=ctx.f(0.05))
    if p.get("caption"):
        hud(ctx, cam, p["caption"], hud_top(ctx) - ctx.u * 0.85, ctx.u * 0.38,
            color="secondary", start=ctx.f(0.12))


@template("abstract", "abstract_field", "shapes", "tunnel")
def t_abstract(ctx, p):
    """Camera glides through a field of floating shapes; optional centered text.
    params: text, count (60), kinds [..], camera_speed (1.0)."""
    world_gradient(ctx)
    n = int(p.get("count", 60))
    kinds = p.get("kinds") or ["icosphere", "torus", "cube", "sphere", "cone", "gem"]
    cols = [ctx.style["primary"], ctx.style["secondary"], ctx.style["accent"]]
    for i in range(n):
        y = ctx.rng.uniform(-2, 40)
        spread = ctx.vw * 0.45 * (1 + (y + 10) / 10)
        x = ctx.rng.uniform(-spread, spread)
        z = ctx.cz + ctx.rng.uniform(-spread, spread) * ctx.res_y / ctx.res_x
        if abs(x) < ctx.vw * 0.25 and y < 8 and p.get("text"):
            x += ctx.vw * 0.4 * (1 if x >= 0 else -1)
        kind = ctx.rng.choice(kinds)
        mat = mat_preset(ctx, ctx.rng.choice(["glossy", "glossy", "metal", "neon" if ctx.dark else "matte"]),
                         ctx.rng.choice(cols))
        o = prim(kind, size=ctx.rng.uniform(0.25, 0.9), loc=(x, y, z), mat=mat,
                 rot=(ctx.rng.uniform(0, 6), ctx.rng.uniform(0, 6), ctx.rng.uniform(0, 6)))
        spin(o, ctx.frames, turns=ctx.rng.uniform(-0.4, 0.4), axis=ctx.rng.choice((0, 1, 2)))
        wobble(o, "location", strength=0.3, scale=50)
    light_rig(ctx, (0, 6, ctx.cz), scale=2.0)
    cam, _ = camera(ctx, "static", target=(0, 30, ctx.cz))
    speed = float(p.get("camera_speed", 1.0))
    key(cam, "location", 1, (0, -ctx.CAM_DIST, ctx.cz), "linear")
    key(cam, "location", ctx.frames, (0, -ctx.CAM_DIST + 6 * speed, ctx.cz), "linear")
    if p.get("text"):
        word_block(ctx, p["text"], ctx.u * 0.95, ctx.cw, center=(0, -ctx.CAM_DIST + 6 * speed + 7, ctx.cz),
                   start_frame=ctx.f(0.05), stagger=3, max_h=ctx.ch * 0.7)


@template("landscape", "terrain", "flyover")
def t_landscape(ctx, p):
    """Low-poly terrain fly-over with water. params: biome (green|desert|snow|alien|volcanic),
    text (screen-locked title), caption, height (3.5)."""
    world_gradient(ctx, ambient=0.6 if ctx.dark else 1.0)
    biomes = {
        "green": ["#1F4E79", "#E3D3A3", "#5E8C31", "#3B5F22", "#7A6A5A", "#FFFFFF"],
        "desert": ["#2E86AB", "#F4D58D", "#E0A458", "#C0763F", "#8C4B2F", "#F6E7CB"],
        "snow": ["#1B3B5A", "#C7D6E3", "#E9F1F7", "#A9B8C6", "#7B8794", "#FFFFFF"],
        "alien": ["#3D1766", "#00F5D4", "#9B5DE5", "#F15BB5", "#FEE440", "#FFFFFF"],
        "volcanic": ["#FF4500", "#2B2B2B", "#3D3D3D", "#1A1A1A", "#5A5A5A", "#888888"],
    }
    pal = biomes.get(p.get("biome", "green"), biomes["green"])
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=90, y_subdivisions=90, size=70, location=(0, 20, 0))
    g = bpy.context.view_layer.objects.active
    tx = bpy.data.textures.new("terrain", "CLOUDS")
    tx.noise_scale = float(p.get("noise_scale", 3.0))
    tx.noise_depth = 3
    d = g.modifiers.new("displace", "DISPLACE")
    d.texture = tx
    d.strength = float(p.get("height", 3.5))
    d.mid_level = 0.45
    m = bpy.data.materials.new("terrain")
    nt = m.node_tree
    b = [n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"][0]
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -1.0
    mr.inputs["From Max"].default_value = d.strength * 0.6
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, hex_rgba(pal[1])
    els[1].position, els[1].color = 0.92, hex_rgba(pal[5])
    for pos, col in ((0.18, pal[2]), (0.5, pal[3]), (0.75, pal[4])):
        e = els.new(pos)
        e.color = hex_rgba(col)
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.85
    g.data.materials.append(m)
    bpy.ops.mesh.primitive_plane_add(size=70, location=(0, 20, 0.15))
    w = bpy.context.view_layer.objects.active
    w.data.materials.append(mat_principled("water", pal[0], rough=0.08, coat=0.5,
                                           emit=0.6 if p.get("biome") == "volcanic" else 0.0))
    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = float(p.get("sun", 3.5))
    sun.color = hex_rgba(ctx.style["key_light"])[:3]
    so = bpy.data.objects.new("sun", sun)
    bpy.context.scene.collection.objects.link(so)
    so.rotation_euler = (math.radians(55), 0, math.radians(30))
    cam, tgt = camera(ctx, "static", target=(0, 10, 1.0))
    cam.data.lens = 28
    key(cam, "location", 1, (0, -14, 6.5), "linear")
    key(cam, "location", ctx.frames, (0, -14 + 9 * float(p.get("camera_speed", 1.0)), 5.5), "linear")
    key(tgt, "location", 1, (0, 10, 0.5), "linear")
    key(tgt, "location", ctx.frames, (0, 19, 0.5), "linear")
    if p.get("text"):
        hud(ctx, cam, p["text"], hud_top(ctx) - ctx.u * 0.3, ctx.u * 0.85, start=ctx.f(0.05))
    if p.get("caption"):
        hud(ctx, cam, p["caption"], hud_top(ctx) - ctx.u * 1.2, ctx.u * 0.4,
            start=ctx.f(0.12), color="text")


@template("city", "skyline", "cityscape")
def t_city(ctx, p):
    """Procedural city with lit windows; camera flies between towers.
    params: text, caption, density (1.0)."""
    world_gradient(ctx, ambient=0.3 if ctx.dark else 0.9)
    if ctx.dark:
        starfield(ctx, 400, 60)
    bm = bpy.data.materials.new("bld")
    nt = bm.node_tree
    b = [n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"][0]
    b.inputs["Base Color"].default_value = hex_rgba(ctx.style["floor"] if ctx.dark else "#BFC6CF")
    b.inputs["Roughness"].default_value = 0.35
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    add = nt.nodes.new("ShaderNodeMath")
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    nt.links.new(sep.outputs["X"], add.inputs[0])
    nt.links.new(sep.outputs["Y"], add.inputs[1])
    nt.links.new(add.outputs[0], comb.inputs["X"])
    nt.links.new(sep.outputs["Z"], comb.inputs["Y"])
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.inputs["Scale"].default_value = 4.0
    br.inputs["Mortar Size"].default_value = 0.12
    br.inputs["Color1"].default_value = hex_rgba(ctx.style["accent"])
    br.inputs["Color2"].default_value = (0, 0, 0, 1)
    br.inputs["Mortar"].default_value = (0, 0, 0, 1)
    nt.links.new(comb.outputs[0], br.inputs["Vector"])
    if b.inputs.get("Emission Color"):
        nt.links.new(br.outputs["Color"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = 3.0 if ctx.dark else 0.3
    floor(ctx, z=0, reflect=True)
    dens = float(p.get("density", 1.0))
    for gx in range(-7, 8):
        for gy in range(-2, 22):
            if gx in (-1, 0, 1) or ctx.rng.random() > 0.8 * dens:
                continue  # avenue down the middle for the camera
            h = ctx.rng.uniform(1.0, 4.0) * (1 + 1.5 * ctx.rng.random() ** 4) * (1 + abs(gx) * 0.12)
            w = ctx.rng.uniform(0.6, 0.9)
            bpy.ops.mesh.primitive_cube_add(size=1, location=(gx * 1.3, gy * 1.3, h / 2))
            o = bpy.context.view_layer.objects.active
            o.scale = (w, w, h)
            o.data.materials.append(bm)
            if ctx.rng.random() < 0.1:
                prim("sphere", size=0.06, loc=(gx * 1.3, gy * 1.3, h + 0.15),
                     mat=mat_emission("beacon", "#FF3355", 20))
    cam, tgt = camera(ctx, "static", target=(0, 20, 1.5))
    cam.data.lens = 24
    sp = float(p.get("camera_speed", 1.0))
    key(cam, "location", 1, (0, -6, 2.2), "linear")
    key(cam, "location", ctx.frames, (0, -6 + 10 * sp, 2.8), "linear")
    key(tgt, "location", 1, (0, 20, 2.5), "linear")
    key(tgt, "location", ctx.frames, (0, 30, 3.2), "linear")
    area_light("moon", (-10, -10, 20), 3000 if not ctx.dark else 800, ctx.style["key_light"], 10, (0, 10, 0))
    if p.get("text"):
        hud(ctx, cam, p["text"], hud_top(ctx) - ctx.u * 0.3, ctx.u * 0.85, start=ctx.f(0.05))
    if p.get("caption"):
        hud(ctx, cam, p["caption"], hud_top(ctx) - ctx.u * 1.2, ctx.u * 0.4, start=ctx.f(0.12))


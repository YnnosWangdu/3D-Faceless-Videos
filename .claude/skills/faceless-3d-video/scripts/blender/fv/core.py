"""Core helpers for the faceless-video Blender renderer.

Everything here is version-tolerant (Blender 4.2 LTS -> 5.x): optional
properties are set through `_try`/`_set_input` so a renamed socket never
crashes a render.
"""
import json
import math
import os
import random

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
STYLES = json.load(open(os.path.join(HERE, "styles.json")))
STYLES.pop("_doc", None)


# --------------------------------------------------------------------------- utils
def _try(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception:
        return None


def hex_rgba(h, alpha=1.0):
    """sRGB hex -> linear RGBA tuple (what Blender colour sockets expect)."""
    if isinstance(h, (list, tuple)):
        return tuple(h) if len(h) == 4 else (*h, alpha)
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, alpha)


def ease(t, kind="inout"):
    t = max(0.0, min(1.0, t))
    if kind == "in":
        return t * t * t
    if kind == "out":
        return 1 - (1 - t) ** 3
    if kind == "back":
        c1, c3 = 1.70158, 2.70158
        return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2
    if kind == "linear":
        return t
    return 3 * t * t - 2 * t * t * t


def link(obj, coll=None):
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj


# --------------------------------------------------------------------------- context
class Ctx:
    """Per-beat build context: timing, framing, palette, RNG."""

    CAM_DIST = 10.0
    LENS = 50.0
    SENSOR = 36.0

    def __init__(self, spec, beat):
        self.spec = spec
        self.beat = beat
        self.fps = int(spec.get("fps", 30))
        self.duration = float(beat["duration"])
        self.frames = max(2, int(round(self.duration * self.fps)))
        self.res_x, self.res_y = spec["resolution"]
        self.portrait = self.res_y > self.res_x
        st = dict(STYLES.get(spec.get("style", "neon"), STYLES["neon"]))
        st.update(spec.get("style_overrides", {}) or {})
        st.update((beat.get("scene") or {}).get("style_overrides", {}) or {})
        self.style = st
        self.dark = st.get("mood", "dark") == "dark"
        self.rng = random.Random(beat.get("seed", hash(beat.get("id", "x")) & 0xFFFF))
        # visible plane at y=0 for the default camera (sensor fit horizontal)
        self.vw = self.CAM_DIST * self.SENSOR / self.LENS
        self.vh = self.vw * self.res_y / self.res_x
        cap = (spec.get("captions") or {}).get("enabled", True)
        if self.portrait:
            # captions live in the lower-middle third in shorts: keep content up top
            self.cz = self.vh * (0.12 if cap else 0.0)
            self.cw, self.ch = self.vw * 0.86, self.vh * (0.46 if cap else 0.7)
        else:
            self.cz = self.vh * (0.06 if cap else 0.0)
            self.cw, self.ch = self.vw * 0.86, self.vh * (0.72 if cap else 0.84)
        self.u = min(self.cw, self.ch * 1.6) / 7.0  # layout unit
        self.font = None
        fp = spec.get("font")
        if fp and os.path.exists(fp):
            self.font = _try(bpy.data.fonts.load, fp)
        self.mats = {}

    def f(self, frac):
        """Fraction of beat (0..1) -> frame number (1-based)."""
        return 1 + int(round(frac * (self.frames - 1)))

    def fs(self, seconds):
        return 1 + int(round(seconds * self.fps))

    def col(self, key):
        v = self.style.get(key, key)
        return hex_rgba(v if isinstance(v, str) and v.startswith("#") else self.style["primary"])


# --------------------------------------------------------------------------- materials
def _bsdf(mat):
    for n in mat.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            return n
    return None


def _set_input(node, name, value):
    if node is None:
        return
    s = node.inputs.get(name)
    if s is not None:
        _try(setattr, s, "default_value", value)


def mat_principled(name, color, rough=0.35, metal=0.0, emit=0.0, coat=0.0,
                   transmission=0.0, alpha=1.0, emit_color=None):
    m = bpy.data.materials.new(name)
    if hasattr(m, "use_nodes") and not m.use_nodes:
        _try(setattr, m, "use_nodes", True)
    b = _bsdf(m)
    c = hex_rgba(color)
    _set_input(b, "Base Color", c)
    _set_input(b, "Roughness", rough)
    _set_input(b, "Metallic", metal)
    _set_input(b, "Coat Weight", coat)
    _set_input(b, "Transmission Weight", transmission)
    if transmission:
        _set_input(b, "IOR", 1.45)
    if emit:
        _set_input(b, "Emission Color", hex_rgba(emit_color or color))
        _set_input(b, "Emission Strength", emit)
    if alpha < 1:
        _set_input(b, "Alpha", alpha)
        _try(setattr, m, "surface_render_method", "BLENDED")
    m.diffuse_color = c
    return m


def mat_emission(name, color, strength=3.0):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = hex_rgba(color)
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    m.diffuse_color = hex_rgba(color)
    return m


def mat_preset(ctx, kind, color):
    """Named looks used by templates: glossy | matte | metal | gold | chrome |
    glass | neon | clay | emissive."""
    key = (kind, color)
    if key in ctx.mats:
        return ctx.mats[key]
    c = color
    if kind == "metal":
        m = mat_principled("metal", c, rough=0.25, metal=1.0)
    elif kind == "gold":
        m = mat_principled("gold", "#E8B83A", rough=0.22, metal=1.0)
    elif kind == "chrome":
        m = mat_principled("chrome", "#E6E6E6", rough=0.05, metal=1.0)
    elif kind == "glass":
        m = mat_principled("glass", c, rough=0.02, transmission=1.0)
    elif kind in ("neon", "emissive"):
        m = mat_principled("neon", c, rough=0.4, emit=4.0 if kind == "neon" else 1.5)
    elif kind in ("matte", "clay"):
        m = mat_principled("clay", c, rough=0.75)
    else:  # glossy
        m = mat_principled("glossy", c, rough=0.18, coat=0.6)
    ctx.mats[key] = m
    return m


def mat_text(ctx, color_key="text"):
    st = ctx.style
    c = st.get(color_key, color_key)
    emit = st.get("text_emit", 0.0) if ctx.dark else 0.0
    return mat_principled("text_" + str(color_key), c, rough=0.3, coat=0.3, emit=emit)


def world_gradient(ctx, ambient=None):
    """Camera sees a screen-space vertical gradient; lighting gets a soft ambient."""
    w = bpy.data.worlds.new("bg")
    bpy.context.scene.world = w
    if hasattr(w, "use_nodes") and not w.use_nodes:
        _try(setattr, w, "use_nodes", True)
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = ctx.col("bg_bottom")
    ramp.color_ramp.elements[1].color = ctx.col("bg_top")
    nt.links.new(tc.outputs["Window"], sep.inputs[0])
    nt.links.new(sep.outputs["Y"], ramp.inputs["Fac"])
    bg_cam = nt.nodes.new("ShaderNodeBackground")
    bg_cam.inputs["Strength"].default_value = 1.0
    nt.links.new(ramp.outputs["Color"], bg_cam.inputs["Color"])
    bg_amb = nt.nodes.new("ShaderNodeBackground")
    amb = ambient if ambient is not None else (0.35 if ctx.dark else 0.9)
    top = ctx.col("bg_top")
    bg_amb.inputs["Color"].default_value = tuple(0.5 * top[i] + 0.25 for i in range(3)) + (1,)
    bg_amb.inputs["Strength"].default_value = amb
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(bg_amb.outputs[0], mix.inputs[1])
    nt.links.new(bg_cam.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return w


# --------------------------------------------------------------------------- objects
def _active():
    return bpy.context.view_layer.objects.active


def smooth(obj, on=True):
    if obj.type != "MESH":
        return obj
    if on and hasattr(obj.data, "shade_smooth"):
        obj.data.shade_smooth()
    elif not on and hasattr(obj.data, "shade_flat"):
        obj.data.shade_flat()
    else:
        for p in obj.data.polygons:
            p.use_smooth = on
    return obj


def bevel(obj, width=0.04, segments=3):
    m = obj.modifiers.new("bevel", "BEVEL")
    m.width = width
    m.segments = segments
    _try(setattr, m, "limit_method", "ANGLE")
    return obj


def prim(kind, size=1.0, loc=(0, 0, 0), mat=None, rot=(0, 0, 0), smooth_shade=True):
    """Primitive factory. kind: sphere cube torus cone cylinder icosphere monkey
    gem crystal ring coin capsule pyramid plane."""
    loc = Vector(loc)
    ops = bpy.ops.mesh
    k = kind
    if k == "sphere":
        ops.primitive_uv_sphere_add(radius=size, location=loc, segments=48, ring_count=24)
    elif k in ("cube", "box"):
        ops.primitive_cube_add(size=size * 1.6, location=loc)
    elif k == "torus":
        ops.primitive_torus_add(major_radius=size, minor_radius=size * 0.32, location=loc,
                                major_segments=64, minor_segments=24)
    elif k == "ring":
        ops.primitive_torus_add(major_radius=size, minor_radius=size * 0.06, location=loc,
                                major_segments=96, minor_segments=12)
    elif k == "cone":
        ops.primitive_cone_add(radius1=size, depth=size * 2, location=loc, vertices=48)
    elif k == "pyramid":
        ops.primitive_cone_add(radius1=size * 1.1, depth=size * 1.8, location=loc, vertices=4)
        smooth_shade = False
    elif k == "cylinder":
        ops.primitive_cylinder_add(radius=size * 0.8, depth=size * 1.8, location=loc, vertices=64)
    elif k == "coin":
        ops.primitive_cylinder_add(radius=size, depth=size * 0.18, location=loc, vertices=96,
                                   rotation=(math.pi / 2, 0, 0))
    elif k == "capsule":
        ops.primitive_uv_sphere_add(radius=size * 0.6, location=loc, segments=32, ring_count=16)
        o = _active()
        o.scale = (1, 1, 1.7)
    elif k in ("icosphere", "gem", "crystal"):
        ops.primitive_ico_sphere_add(radius=size, subdivisions=1 if k != "icosphere" else 3,
                                     location=loc)
        if k == "crystal":
            _active().scale = (0.6, 0.6, 1.5)
        if k != "icosphere":
            smooth_shade = False
    elif k == "monkey":
        ops.primitive_monkey_add(size=size * 1.6, location=loc)
        o = _active()
        o.modifiers.new("subd", "SUBSURF").levels = 2
    elif k == "plane":
        ops.primitive_plane_add(size=size, location=loc)
        smooth_shade = False
    else:
        ops.primitive_cube_add(size=size * 1.6, location=loc)
    o = _active()
    o.rotation_euler = rot if k != "coin" else o.rotation_euler
    if k in ("cube", "box", "cylinder", "coin"):
        bevel(o, width=size * 0.06, segments=4)
        smooth_shade = False
        _try(o.data.shade_auto_smooth) if hasattr(o.data, "shade_auto_smooth") else None
    smooth(o, smooth_shade)
    if mat:
        o.data.materials.append(mat)
    return o


def text(ctx, body, size=1.0, mat=None, loc=(0, 0, 0), extrude=None, bevel_depth=None,
         align="CENTER", wrap=None, max_w=None, max_h=None, face_cam=True, name="txt"):
    """3D text standing in the XZ plane facing the default camera (-Y)."""
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = str(body)
    cu.size = size
    cu.extrude = size * 0.12 if extrude is None else extrude
    cu.bevel_depth = size * 0.025 if bevel_depth is None else bevel_depth
    cu.bevel_resolution = 3
    cu.align_x = align
    cu.align_y = "CENTER"
    cu.space_line = 0.95
    if ctx.font:
        cu.font = ctx.font
        _try(setattr, cu, "font_bold", ctx.font)
    if wrap:
        cu.text_boxes[0].width = wrap
        cu.text_boxes[0].x = -wrap / 2 if align == "CENTER" else 0
    o = bpy.data.objects.new(name, cu)
    link(o)
    o.location = loc
    if face_cam:
        o.rotation_euler = (math.pi / 2, 0, 0)
    o.data.materials.append(mat or mat_text(ctx))
    fit(o, max_w, max_h)
    return o


def dims(o):
    bpy.context.view_layer.update()
    return o.dimensions.copy()


def fit(o, max_w=None, max_h=None):
    if not (max_w or max_h):
        return o
    d = dims(o)
    s = 1.0
    if max_w and d.x > max_w:
        s = min(s, max_w / d.x)
    # text objects are rotated, so their on-screen height is local Y
    h = d.y if o.type == "FONT" else d.z
    if max_h and h > max_h:
        s = min(s, max_h / h)
    if s < 1.0:
        o.scale = (o.scale[0] * s, o.scale[1] * s, o.scale[2] * s)
    return o


def empty(name="target", loc=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    e.location = loc
    link(e)
    return e


def starfield(ctx, count=500, radius=40, size=0.04, color="#FFFFFF", strength=6.0):
    """One mesh of many tiny emissive tetrahedra: cheap, render-friendly stars."""
    import bmesh
    me = bpy.data.meshes.new("stars")
    bm = bmesh.new()
    rng = ctx.rng
    for _ in range(count):
        v = Vector((rng.gauss(0, 1), abs(rng.gauss(0, 1)) + 0.3, rng.gauss(0, 1))).normalized()
        c = v * radius * rng.uniform(0.7, 1.0)
        s = size * rng.uniform(0.5, 1.6) * radius / 40
        geo = bmesh.ops.create_icosphere(bm, subdivisions=0, radius=s)
        bmesh.ops.translate(bm, vec=c, verts=geo["verts"])
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new("stars", me)
    link(o)
    o.data.materials.append(mat_emission("star", color, strength))
    _try(setattr, o, "visible_shadow", False)
    return o


# --------------------------------------------------------------------------- animation
def fcurves(id_data):
    ad = id_data.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    if hasattr(act, "fcurves") and not hasattr(act, "layers"):
        return list(act.fcurves)
    try:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(act, ad.action_slot)
        if cb:
            return list(cb.fcurves)
    except Exception:
        pass
    out = []
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for cb in getattr(strip, "channelbags", []):
                out += list(cb.fcurves)
    if not out and hasattr(act, "fcurves"):
        out = list(act.fcurves)
    return out


_INTERP = {"linear": ("LINEAR", "AUTO"), "inout": ("BEZIER", "AUTO"),
           "out": ("CUBIC", "EASE_OUT"), "in": ("CUBIC", "EASE_IN"),
           "back": ("BACK", "EASE_OUT"), "bounce": ("BOUNCE", "EASE_OUT"),
           "elastic": ("ELASTIC", "EASE_OUT"), "expo": ("EXPO", "EASE_OUT"),
           "const": ("CONSTANT", "AUTO")}


def key(obj, path, frame, value=None, ease_kind="inout"):
    """Insert a key; `ease_kind` shapes the segment that STARTS at this key."""
    if value is not None:
        cur = getattr(obj, path)
        if hasattr(cur, "__len__") and not hasattr(value, "__len__"):
            value = [value] * len(cur)
        setattr(obj, path, value)
    obj.keyframe_insert(path, frame=frame)
    interp, easing = _INTERP.get(ease_kind, _INTERP["inout"])
    for fc in fcurves(obj):
        if fc.data_path != path:
            continue
        for kp in fc.keyframe_points:
            if abs(kp.co[0] - frame) < 0.01:
                kp.interpolation = interp
                _try(setattr, kp, "easing", easing)
                if interp == "BACK":
                    _try(setattr, kp, "back", 1.6)


def pop_in(obj, frame, dur=10, kind="back", from_scale=0.0):
    target = tuple(obj.scale)
    key(obj, "scale", max(1, frame - 1), tuple(s * from_scale for s in target), "const")
    key(obj, "scale", frame, tuple(s * from_scale for s in target), kind)
    key(obj, "scale", frame + dur, target, "inout")
    return obj


def pop_out(obj, frame, dur=8):
    target = tuple(obj.scale)
    key(obj, "scale", frame, target, "in")
    key(obj, "scale", frame + dur, (0, 0, 0), "const")


def slide_in(obj, frame, offset=(0, 0, -1), dur=14, kind="out"):
    end = obj.location.copy()
    start = end + Vector(offset)
    key(obj, "location", max(1, frame - 1), start, "const")
    key(obj, "location", frame, start, kind)
    key(obj, "location", frame + dur, end, "inout")
    return obj


def show_between(obj, f0, f1=None):
    """Visibility window via hide_render keys (works in every engine)."""
    obj.hide_render = True
    obj.keyframe_insert("hide_render", frame=1)
    obj.hide_render = False
    obj.keyframe_insert("hide_render", frame=max(1, f0))
    if f1 is not None:
        obj.hide_render = True
        obj.keyframe_insert("hide_render", frame=f1)
    for fc in fcurves(obj):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"
    obj.hide_render = f0 > 1


def spin(obj, frames, turns=1.0, axis=2, start=None):
    base = obj.rotation_euler.copy()
    v0 = base[axis] if start is None else start
    key_idx(obj, "rotation_euler", axis, 1, v0, "linear")
    key_idx(obj, "rotation_euler", axis, frames, v0 + turns * 2 * math.pi, "linear")
    _extrapolate(obj, "rotation_euler")


def key_idx(obj, path, idx, frame, value, ease_kind="inout"):
    getattr(obj, path)[idx] = value
    obj.keyframe_insert(path, index=idx, frame=frame)
    interp, easing = _INTERP.get(ease_kind, _INTERP["inout"])
    for fc in fcurves(obj):
        if fc.data_path == path and fc.array_index == idx:
            for kp in fc.keyframe_points:
                if abs(kp.co[0] - frame) < 0.01:
                    kp.interpolation = interp
                    _try(setattr, kp, "easing", easing)


def _extrapolate(obj, path):
    for fc in fcurves(obj):
        if fc.data_path == path:
            fc.extrapolation = "LINEAR"


def wobble(obj, path="location", strength=0.08, scale=40.0, indices=(0, 1, 2), phase=None):
    """Organic idle motion via an F-curve noise modifier."""
    if not obj.animation_data or not any(fc.data_path == path for fc in fcurves(obj)):
        obj.keyframe_insert(path, frame=1)
    for fc in fcurves(obj):
        if fc.data_path == path and fc.array_index in indices:
            m = fc.modifiers.new("NOISE")
            m.strength = strength
            m.scale = scale
            m.phase = phase if phase is not None else random.uniform(0, 100)


# --------------------------------------------------------------------------- camera & lights
def camera(ctx, move="push", target=(0, 0, 0), dist=None, height=0.0, lens=None, orbit_deg=40,
           tilt=0.0):
    """Camera that always looks at an empty. Moves: push pull static orbit drift crane
    dolly_through."""
    dist = dist or ctx.CAM_DIST
    tgt = empty("cam_target", Vector(target))
    cd = bpy.data.cameras.new("cam")
    cd.lens = lens or ctx.LENS
    cd.sensor_fit = "HORIZONTAL"
    cd.sensor_width = ctx.SENSOR
    cd.clip_end = 500
    cam = bpy.data.objects.new("cam", cd)
    link(cam)
    bpy.context.scene.camera = cam
    c = cam.constraints.new("TRACK_TO")
    c.target = tgt
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    T = Vector(target)
    F = ctx.frames
    base = T + Vector((0, -dist, height + tilt))
    if move == "push":
        key(cam, "location", 1, base + Vector((0, -dist * 0.06, 0)), "linear")
        key(cam, "location", F, base + Vector((0, dist * 0.07, 0)), "linear")
    elif move == "pull":
        key(cam, "location", 1, base + Vector((0, dist * 0.06, 0)), "linear")
        key(cam, "location", F, base + Vector((0, -dist * 0.07, 0)), "linear")
    elif move == "orbit":
        piv = empty("cam_pivot", T)
        cam.parent = piv
        cam.location = Vector((0, -dist, height + tilt))
        a = math.radians(orbit_deg) / 2
        key_idx(piv, "rotation_euler", 2, 1, -a, "linear")
        key_idx(piv, "rotation_euler", 2, F, a, "linear")
    elif move == "drift":
        key(cam, "location", 1, base + Vector((-dist * 0.06, 0, 0)), "linear")
        key(cam, "location", F, base + Vector((dist * 0.06, 0, 0)), "linear")
    elif move == "crane":
        key(cam, "location", 1, base + Vector((0, 0, -dist * 0.08)), "linear")
        key(cam, "location", F, base + Vector((0, dist * 0.04, dist * 0.08)), "linear")
    else:  # static
        cam.location = base
    return cam, tgt


def area_light(name, loc, energy, color, size=4.0, target=(0, 0, 0)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy
    ld.color = hex_rgba(color)[:3]
    ld.size = size
    o = bpy.data.objects.new(name, ld)
    link(o)
    o.location = loc
    d = Vector(target) - Vector(loc)
    o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return o


def light_rig(ctx, center=(0, 0, 0), scale=1.0):
    st = ctx.style
    c = Vector(center)
    k = 1.0 if ctx.dark else 1.4
    area_light("key", c + Vector((-5, -6, 5)) * scale, 900 * k * scale ** 2, st["key_light"], 6 * scale, c)
    rim = area_light("rim", c + Vector((6, 4, 3)) * scale, 700 * scale ** 2, st["rim_light"], 4 * scale, c)
    _try(setattr, rim, "visible_glossy", False)  # no hot square reflected in glossy floors
    area_light("fill", c + Vector((6, -6, -1)) * scale, 250 * k * scale ** 2, "#FFFFFF", 8 * scale, c)


def floor(ctx, z=0.0, size=200, reflect=True):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, z))
    o = _active()
    o.name = "floor"
    o.data.materials.append(mat_principled("floor", ctx.style["floor"],
                                           rough=0.32 if reflect else 0.8, coat=0.2 if reflect else 0))
    return o


def ambient_shapes(ctx, count=14, depth=(6, 18), spread=1.3, kinds=("icosphere", "torus", "cube", "sphere")):
    """Drifting background props for depth & motion."""
    out = []
    st = ctx.style
    cols = [st["primary"], st["secondary"], st["accent"]]
    for i in range(count):
        y = ctx.rng.uniform(*depth)
        w = (ctx.vw * (ctx.CAM_DIST + y) / ctx.CAM_DIST) * spread
        h = w * ctx.res_y / ctx.res_x
        x = ctx.rng.uniform(-w / 2, w / 2)
        z = ctx.cz + ctx.rng.uniform(-h / 2, h / 2)
        k = ctx.rng.choice(kinds)
        col = ctx.rng.choice(cols)
        m = mat_preset(ctx, "neon" if (ctx.dark and ctx.rng.random() < 0.3) else "glossy", col)
        o = prim(k, size=ctx.rng.uniform(0.2, 0.6), loc=(x, y, z), mat=m,
                 rot=(ctx.rng.uniform(0, 6), ctx.rng.uniform(0, 6), 0))
        spin(o, ctx.frames, turns=ctx.rng.uniform(-0.25, 0.25), axis=ctx.rng.choice((0, 2)))
        wobble(o, "location", strength=0.25, scale=60)
        out.append(o)
    return out


# --------------------------------------------------------------------------- kinetic words
def word_block(ctx, sentence, size, max_w, center=(0, 0, 0), line_gap=1.25, start_frame=1,
               stagger=3, highlight_mat=None, base_mat=None, anim="pop", max_lines=None,
               max_h=None):
    """Lay out a sentence as individual 3D words (centered, wrapped), each animating in.
    Words wrapped in *asterisks* use the highlight material."""
    words = sentence.split()
    base_mat = base_mat or mat_text(ctx)
    highlight_mat = highlight_mat or mat_text(ctx, "accent")
    objs = []
    for w in words:
        hi = w.startswith("*") and w.rstrip(".,!?:;").endswith("*")
        clean = w.replace("*", "")
        o = text(ctx, clean, size=size, mat=highlight_mat if hi else base_mat, name="w")
        objs.append((o, dims(o).x))
    space = size * 0.32
    lines, cur, cur_w = [], [], 0.0
    for o, w in objs:
        add = w if not cur else w + space
        if cur and cur_w + add > max_w:
            lines.append((cur, cur_w))
            cur, cur_w = [], 0.0
            add = w
        cur.append((o, w))
        cur_w += add
    if cur:
        lines.append((cur, cur_w))
    if max_lines and len(lines) > max_lines:
        # too many lines: shrink and re-flow with a wider virtual box
        for o, _ in objs:
            bpy.data.objects.remove(o)
        return word_block(ctx, sentence, size * 0.85, max_w, center, line_gap, start_frame,
                          stagger, highlight_mat, base_mat, anim, max_lines, max_h)
    widest = max(lw for _, lw in lines)
    scale = min(1.0, max_w / widest) if widest > 0 else 1.0
    if max_h:
        need = size * line_gap * (len(lines) - 1) + size
        scale = min(scale, max_h / need)
    lh = size * line_gap * scale
    cx, cy, cz = center
    total_h = lh * (len(lines) - 1)
    i = 0
    for li, (line, lw) in enumerate(lines):
        x = cx - lw * scale / 2
        z = cz + total_h / 2 - li * lh
        for o, w in line:
            o.scale = (scale, scale, scale)
            o.location = (x + w * scale / 2, cy, z)
            x += (w + space) * scale
            f = start_frame + i * stagger
            if anim == "slide":
                slide_in(o, f, offset=(0, 0, -size * 0.8), dur=10)
                pop_in(o, f, dur=8, kind="out")
            elif anim == "drop":
                slide_in(o, f, offset=(0, 0, size * 1.2), dur=12, kind="bounce")
                pop_in(o, f, dur=6, kind="out")
            elif anim != "none":
                pop_in(o, f, dur=10)
            i += 1
    return [o for o, _ in objs], total_h + size * scale


def hud(ctx, cam, body, y, size, color="text", max_w=None, start=1, anim="pop", align="CENTER",
        x=0.0, mat=None):
    """Screen-locked 3D text (parented to the camera) for titles and labels; stays put
    whatever the camera does. y/x/size are in the same units as the y=0 content plane."""
    d = 3.0
    k = d / (ctx.CAM_DIST * cam.data.lens / ctx.LENS)
    o = text(ctx, body, size=size * k, mat=mat or mat_text(ctx, color), face_cam=False,
             max_w=(max_w or ctx.cw) * k, align=align, name="hud")
    o.parent = cam
    o.location = (x * k, y * k, -d)
    for vis in ("visible_glossy", "visible_shadow", "visible_diffuse", "visible_transmission"):
        _try(setattr, o, vis, False)  # overlay only: no reflections/shadows of HUD text
    if anim == "pop":
        pop_in(o, start, dur=10)
    elif anim == "slide":
        slide_in(o, start, offset=(0, -size * k * 0.8, 0), dur=12)
        pop_in(o, start, dur=8, kind="out")
    return o


def hud_top(ctx):
    return ctx.vh / 2 - ctx.vh * (0.13 if ctx.portrait else 0.12)

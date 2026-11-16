"""Render storyboard beats to PNG frame sequences (or single preview stills).

Run inside Blender:
    blender -b --factory-startup -P render_beats.py -- --spec render_spec.json [--stills]
or with the `bpy` pip module:
    python render_beats.py --spec render_spec.json

The render spec is written by make_video.py (it adds measured beat durations,
resolution, output folders). You normally never call this directly.
"""
import argparse
import json
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from fv.core import Ctx, _try  # noqa: E402
from fv.templates import TEMPLATES  # noqa: E402

QUALITY = {
    #           res%, cycles spp, eevee spp, motion blur
    "draft":    (50, 6, 16, False),
    "standard": (100, 40, 64, False),
    "high":     (100, 128, 128, True),
}


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--beats", default="", help="comma separated beat ids (default all)")
    ap.add_argument("--stills", action="store_true", help="one preview still per beat")
    ap.add_argument("--save-blend", action="store_true", help="also save each beat as .blend")
    ap.add_argument("--probe", action="store_true", help="render one tiny frame and exit")
    return ap.parse_args(argv)


def set_first(obj, attr, values):
    """Set the first value Blender accepts (enum names differ between versions)."""
    for v in values:
        try:
            setattr(obj, attr, v)
            return v
        except Exception:
            continue
    return None


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def set_engine(sc, engine, q):
    res, cyc, eev, mblur = QUALITY.get(q, QUALITY["standard"])
    engine = engine.lower()
    if engine == "eevee":
        set_first(sc.render, "engine", ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"))
        _try(setattr, sc.eevee, "taa_render_samples", eev)
        _try(setattr, sc.eevee, "use_raytracing", q != "draft")
        _try(setattr, sc.eevee, "use_shadows", True)
        _try(setattr, sc.eevee, "use_gtao", True)
    elif engine == "workbench":
        sc.render.engine = "BLENDER_WORKBENCH"
        _try(setattr, sc.display.shading, "light", "STUDIO")
        _try(setattr, sc.display.shading, "color_type", "MATERIAL")
    else:
        sc.render.engine = "CYCLES"
        c = sc.cycles
        c.samples = cyc
        _try(setattr, c, "use_adaptive_sampling", True)
        _try(setattr, c, "use_denoising", True)
        _try(setattr, c, "denoiser", "OPENIMAGEDENOISE")
        _try(setattr, c, "max_bounces", 6)
        _try(setattr, c, "transparent_max_bounces", 8)
        _try(setattr, c, "caustics_reflective", False)
        _try(setattr, c, "caustics_refractive", False)
        _try(setattr, c, "blur_glossy", 1.0)
        enable_gpu(sc)
        sc.render.use_persistent_data = True
    sc.render.resolution_percentage = res
    sc.render.use_motion_blur = mblur


def enable_gpu(sc):
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
    except Exception:
        return
    for t in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
        try:
            prefs.compute_device_type = t
            prefs.get_devices()
            devs = [d for d in prefs.devices if d.type == t]
            if devs:
                for d in devs:
                    d.use = True
                sc.cycles.device = "GPU"
                print(f"[fv] Cycles using GPU ({t})")
                return
        except Exception:
            continue


def color_management(sc):
    _try(setattr, sc.view_settings, "view_transform", "AgX")
    set_first(sc.view_settings, "look", ("AgX - Medium High Contrast", "Medium High Contrast",
                                         "AgX - Punchy", "Punchy"))
    sc.view_settings.exposure = 0.0


def add_glow(sc, strength):
    if strength <= 0:
        return
    try:
        if hasattr(sc, "compositing_node_group"):  # Blender 5.x
            ng = bpy.data.node_groups.new("fv_comp", "CompositorNodeTree")
            ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
            rl = ng.nodes.new("CompositorNodeRLayers")
            out = ng.nodes.new("NodeGroupOutput")
            g = ng.nodes.new("CompositorNodeGlare")
            for name, val in (("Type", "Bloom"), ("Quality", "Medium"), ("Threshold", 0.8),
                              ("Strength", strength), ("Size", 0.6)):
                s = g.inputs.get(name)
                if s is not None:
                    _try(setattr, s, "default_value", val)
            ng.links.new(rl.outputs["Image"], g.inputs["Image"])
            ng.links.new(g.outputs[0], out.inputs[0])
            sc.compositing_node_group = ng
        else:  # Blender 4.x
            sc.use_nodes = True
            nt = sc.node_tree
            nt.nodes.clear()
            rl = nt.nodes.new("CompositorNodeRLayers")
            comp = nt.nodes.new("CompositorNodeComposite")
            g = nt.nodes.new("CompositorNodeGlare")
            set_first(g, "glare_type", ("BLOOM", "FOG_GLOW"))
            g.threshold = 0.8
            _try(setattr, g, "mix", -1 + min(1.0, strength))
            _try(setattr, g, "size", 7)
            nt.links.new(rl.outputs["Image"], g.inputs["Image"])
            nt.links.new(g.outputs["Image"], comp.inputs["Image"])
        sc.render.use_compositing = True
        # GPU compositing needs a display/GPU context; CPU works everywhere
        _try(setattr, sc.render, "compositor_device", "CPU")
    except Exception as e:  # glow is cosmetic: never fail a render on it
        print("[fv] glow skipped:", e)


def build(spec, beat):
    reset()
    ctx = Ctx(spec, beat)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = ctx.res_x, ctx.res_y
    sc.render.fps = ctx.fps
    sc.frame_start, sc.frame_end = 1, ctx.frames
    scene = beat.get("scene") or {"template": "title", "text": beat.get("narration", "")[:60]}
    name = scene.get("template", "title")
    fn = TEMPLATES.get(name)
    if fn is None:
        raise ValueError(f"unknown template '{name}'. Known: {sorted(TEMPLATES)}")
    fn(ctx, scene)
    set_engine(sc, spec.get("engine", "eevee"), spec.get("quality", "standard"))
    color_management(sc)
    add_glow(sc, float(ctx.style.get("glow", 0)) * float(scene.get("glow", 1.0)))
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    _try(setattr, sc.render.image_settings, "compression", 15)
    sc.render.use_lock_interface = True
    sc.frame_set(1)
    return ctx, scene


def main():
    a = parse()
    spec = json.load(open(a.spec))
    out = spec["out_dir"]
    if a.probe:
        reset()
        sc = bpy.context.scene
        sc.render.resolution_x, sc.render.resolution_y = 64, 64
        set_engine(sc, spec.get("engine", "eevee"), "draft")
        bpy.ops.mesh.primitive_cube_add()
        cd = bpy.data.cameras.new("c")
        co = bpy.data.objects.new("c", cd)
        sc.collection.objects.link(co)
        co.location = (0, -6, 0)
        co.rotation_euler = (1.5708, 0, 0)
        sc.camera = co
        sc.render.filepath = os.path.join(out, "probe.png")
        bpy.ops.render.render(write_still=True)
        print("[fv] PROBE_OK", sc.render.engine)
        return
    want = [b for b in a.beats.split(",") if b]
    failed = []
    for beat in spec["beats"]:
        if want and beat["id"] not in want:
            continue
        t0 = time.time()
        try:
            ctx, scene = build(spec, beat)
            sc = bpy.context.scene
            if a.stills:
                fr = ctx.f(float(scene.get("still_at", 0.6)))
                sc.frame_set(fr)
                sc.render.filepath = os.path.join(out, "stills", f"{beat['id']}.png")
                bpy.ops.render.render(write_still=True)
            else:
                d = os.path.join(out, "frames", beat["id"])
                os.makedirs(d, exist_ok=True)
                for f in os.listdir(d):
                    if f.endswith(".png") or f == ".done":
                        os.remove(os.path.join(d, f))
                sc.render.filepath = os.path.join(d, "")
                bpy.ops.render.render(animation=True)
                with open(os.path.join(d, ".done"), "w") as fh:
                    json.dump({"frames": ctx.frames, "hash": beat.get("hash", "")}, fh)
            if a.save_blend:
                bd = os.path.join(out, "blend")
                os.makedirs(bd, exist_ok=True)
                bpy.ops.wm.save_as_mainfile(filepath=os.path.join(bd, f"{beat['id']}.blend"))
            print(f"[fv] beat {beat['id']} ({scene.get('template')}) done in {time.time() - t0:.1f}s",
                  flush=True)
        except Exception:
            traceback.print_exc()
            failed.append(beat["id"])
            print(f"[fv] beat {beat['id']} FAILED", flush=True)
    if failed:
        print("[fv] FAILED_BEATS", ",".join(failed))
        sys.exit(3)


if __name__ == "__main__":
    main()

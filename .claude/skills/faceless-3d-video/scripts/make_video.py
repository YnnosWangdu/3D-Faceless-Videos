#!/usr/bin/env python3
"""Faceless 3D video pipeline: storyboard.json -> voiceover -> Blender -> captions -> MP4.

    python make_video.py STORYBOARD.json                       # everything
    python make_video.py STORYBOARD.json --stage validate      # lint + length estimate
    python make_video.py STORYBOARD.json --stage stills        # 1 preview frame per beat + contact sheet
    python make_video.py STORYBOARD.json --quality draft       # fast low-res full video
    python make_video.py STORYBOARD.json --beats hook,fact2    # re-render only some beats
    python make_video.py STORYBOARD.json --stage assemble      # re-mux after editing captions/music

Stages run in order: validate -> tts -> (stills | render) -> assemble.
Everything is cached in <storyboard dir>/build; edit a beat and only that beat re-renders.
"""
import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import captions  # noqa: E402
import tts  # noqa: E402

RENDER_SCRIPT = os.path.join(HERE, "blender", "render_beats.py")
STYLES = json.load(open(os.path.join(HERE, "blender", "fv", "styles.json")))
FORMATS = {"shorts": (1080, 1920), "vertical": (1080, 1920), "reels": (1080, 1920),
           "tiktok": (1080, 1920), "landscape": (1920, 1080), "youtube": (1920, 1080),
           "square": (1080, 1080), "4k": (3840, 2160)}


def log(*a):
    print("[make_video]", *a, flush=True)


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-3000:])
        raise SystemExit(f"command failed: {' '.join(map(str, cmd[:6]))} ...")
    return r


def h(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:12]


def template_names():
    src = open(os.path.join(HERE, "blender", "fv", "templates.py")).read()
    names = set()
    for m in re.finditer(r"@template\(([^)]*)\)", src):
        names.update(re.findall(r'"([^"]+)"', m.group(1)))
    return names


# ------------------------------------------------------------------ blender discovery
def find_blender(explicit=None):
    """Return a command prefix: [blender, -b, ...] or [python] for the bpy module."""
    cands = [explicit, os.environ.get("BLENDER"), os.environ.get("BLENDER_BIN"), shutil.which("blender")]
    cands += sorted(glob.glob("/Applications/Blender*.app/Contents/MacOS/Blender"), reverse=True)
    cands += sorted(glob.glob(r"C:\Program Files\Blender Foundation\Blender*\blender.exe"), reverse=True)
    cands += sorted(glob.glob(os.path.expanduser("~/blender*/blender")), reverse=True)
    cands += sorted(glob.glob("/opt/blender*/blender"), reverse=True) + ["/snap/bin/blender"]
    for c in cands:
        if c and os.path.exists(c):
            if os.path.basename(c).lower().startswith("python"):
                return [c]
            return [c, "-b", "--factory-startup", "-noaudio", "-P"]
    for py in (os.environ.get("FV_BPY_PYTHON"), sys.executable):
        if py and subprocess.run([py, "-c", "import bpy"], capture_output=True).returncode == 0:
            return [py]
    return None


def blender_cmd(prefix, args):
    if len(prefix) == 1:  # bpy module
        return prefix + [RENDER_SCRIPT] + args
    return prefix + [RENDER_SCRIPT, "--"] + args


def run_blender(prefix, args, log_path):
    cmd = blender_cmd(prefix, args)
    with open(log_path, "a") as lf:
        lf.write("\n$ " + " ".join(cmd) + "\n")
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in p.stdout:
            lf.write(line)
            if line.startswith("[fv]") or "Error" in line or "Traceback" in line:
                print("   ", line.rstrip(), flush=True)
        return p.wait()


def pick_engine(prefix, want, build):
    if want != "auto":
        return want
    cache = os.path.join(build, "engine.txt")
    if os.path.exists(cache):
        return open(cache).read().strip()
    spec = os.path.join(build, "probe_spec.json")
    json.dump({"out_dir": build, "engine": "eevee", "beats": []}, open(spec, "w"))
    ok = run_blender(prefix, ["--spec", spec, "--probe"], os.path.join(build, "blender.log")) == 0 \
        and os.path.exists(os.path.join(build, "probe.png"))
    eng = "eevee" if ok else "cycles"
    if not ok:
        log("EEVEE unavailable here (no GPU/display) -> using Cycles (slower, CPU-safe)")
    open(cache, "w").write(eng)
    return eng


# ------------------------------------------------------------------ stages
def load(path):
    sb = json.load(open(path))
    sb.setdefault("format", "shorts")
    sb.setdefault("style", "neon")
    sb.setdefault("fps", 30)
    for i, b in enumerate(sb.get("beats", [])):
        b.setdefault("id", f"b{i + 1:02d}")
    return sb


def validate(sb):
    probs, names = [], template_names()
    ids = set()
    if sb["format"] not in FORMATS and not isinstance(sb.get("resolution"), list):
        probs.append(f"unknown format '{sb['format']}' (use {', '.join(FORMATS)})")
    if sb["style"] not in STYLES:
        probs.append(f"unknown style '{sb['style']}' (use {', '.join(k for k in STYLES if k != '_doc')})")
    total = 0.0
    for b in sb.get("beats", []):
        if b["id"] in ids:
            probs.append(f"duplicate beat id {b['id']}")
        ids.add(b["id"])
        if not re.fullmatch(r"[A-Za-z0-9_-]+", b["id"]):
            probs.append(f"beat id '{b['id']}' must be letters/digits/_/-")
        t = (b.get("scene") or {}).get("template", "title")
        if t not in names:
            probs.append(f"{b['id']}: unknown template '{t}'")
        n = len(tts.clean(b.get("narration", "")).split())
        est = n / tts.WPS + 0.45 if n else float(b.get("duration", 0) or 0)
        if not n and not b.get("duration") and not b.get("audio"):
            probs.append(f"{b['id']}: no narration and no duration")
        if est > 12:
            probs.append(f"{b['id']}: ~{est:.0f}s is long for one visual - split it (aim 2-8 s)")
        img = (b.get("scene") or {}).get("image")
        if img and not os.path.exists(img):
            probs.append(f"{b['id']}: image not found: {img}")
        total += max(est, float(b.get("min_duration", 0) or 0))
    return probs, total


def do_tts(sb, build, force=False, beats=None):
    os.makedirs(os.path.join(build, "audio"), exist_ok=True)
    voice = sb.get("voice", {})
    align = (sb.get("captions") or {}).get("align")
    timeline, t = [], 0.0
    for b in sb["beats"]:
        nar = b.get("narration", "").strip()
        wav = os.path.join(build, "audio", f"{b['id']}.wav")
        meta_p = wav[:-4] + ".json"
        key = h([nar, voice, b.get("audio"), align])
        meta = json.load(open(meta_p)) if os.path.exists(meta_p) else {}
        stale = force or meta.get("key") != key or not os.path.exists(wav)
        if (nar or b.get("audio")) and stale and (not beats or b["id"] in beats or not meta):
            if b.get("audio"):
                meta = tts.from_file(b["audio"], nar, wav)
            else:
                try:
                    meta = tts.synth(nar, wav, voice)
                except RuntimeError as e:
                    raise SystemExit(f"voice for beat '{b['id']}' failed: {e}")
            if align == "whisper" and meta["backend"] != "silent":
                try:
                    ww = tts.whisper_align(wav, nar)
                    script_words = tts.clean(nar).split()
                    if len(ww) == len(script_words):  # keep script spelling, use whisper timing
                        for w, s in zip(ww, script_words):
                            w["w"] = s
                    meta["words"] = ww or meta["words"]
                except Exception as e:
                    log(f"whisper alignment skipped: {e}")
            meta["key"] = key
            json.dump(meta, open(meta_p, "w"), indent=1)
            log(f"voice {b['id']}: {meta['duration']:.2f}s via {meta['backend']}")
        elif not (nar or b.get("audio")):
            meta = {"duration": 0.0, "words": []}
        lead = float(b.get("lead", sb.get("lead", 0.12)))
        pad = float(b.get("pad", sb.get("pad", 0.35)))
        speech = meta.get("duration", 0.0)
        dur = max(speech + lead + pad if speech else 0.0, float(b.get("duration", 0) or 0),
                  float(b.get("min_duration", 0) or 0), 1.0)
        words = [{"w": w["w"], "start": t + lead + w["start"], "end": t + lead + w["end"]}
                 for w in meta.get("words", [])]
        timeline.append({"id": b["id"], "start": t, "duration": dur, "lead": lead,
                         "speech": speech, "words": words})
        t += dur
    json.dump(timeline, open(os.path.join(build, "timeline.json"), "w"), indent=1)
    log(f"timeline: {len(timeline)} beats, {t:.1f}s total")
    return timeline


def render_spec(sb, build, timeline, engine, quality):
    W, H = sb.get("resolution") or FORMATS.get(sb["format"], FORMATS["shorts"])
    beats = []
    for b, tl in zip(sb["beats"], timeline):
        scene = b.get("scene") or {"template": "title", "text": b.get("narration", "")[:60]}
        spec_b = {"id": b["id"], "duration": tl["duration"], "scene": scene,
                  "seed": b.get("seed", int(hashlib.md5(b["id"].encode()).hexdigest()[:6], 16))}
        spec_b["hash"] = h([spec_b, sb["style"], sb.get("style_overrides"), [W, H], sb["fps"], engine,
                            quality, sb.get("font"), (sb.get("captions") or {}).get("enabled", True)])
        beats.append(spec_b)
    spec = {"fps": sb["fps"], "resolution": [W, H], "style": sb["style"],
            "style_overrides": sb.get("style_overrides", {}), "font": sb.get("font"),
            "captions": sb.get("captions", {}), "engine": engine, "quality": quality,
            "out_dir": build, "beats": beats}
    p = os.path.join(build, "render_spec.json")
    json.dump(spec, open(p, "w"), indent=1)
    return spec, p


def beat_done(build, b):
    d = os.path.join(build, "frames", b["id"])
    m = os.path.join(d, ".done")
    if not os.path.exists(m):
        return False
    info = json.load(open(m))
    n = len(glob.glob(os.path.join(d, "*.png")))
    return info.get("hash") == b["hash"] and n >= info.get("frames", 1)


def do_render(prefix, spec, spec_p, build, only=None, force=False, save_blend=False):
    todo = [b["id"] for b in spec["beats"]
            if (not only or b["id"] in only) and (force or not beat_done(build, b))]
    if not todo:
        log("all beats already rendered (cached)")
        return
    frames = sum(int(round(b["duration"] * spec["fps"])) for b in spec["beats"] if b["id"] in todo)
    log(f"rendering {len(todo)} beat(s), {frames} frames, engine={spec['engine']} quality={spec['quality']}")
    t0 = time.time()
    args = ["--spec", spec_p, "--beats", ",".join(todo)] + (["--save-blend"] if save_blend else [])
    run_blender(prefix, args, os.path.join(build, "blender.log"))
    bad = [b["id"] for b in spec["beats"] if b["id"] in todo and not beat_done(build, b)]
    if bad:
        raise SystemExit(f"beats failed to render: {bad} - see {os.path.join(build, 'blender.log')}")
    log(f"render finished in {(time.time() - t0) / 60:.1f} min")


def do_stills(prefix, spec, spec_p, build, only=None):
    d = os.path.join(build, "stills")
    os.makedirs(d, exist_ok=True)
    args = ["--spec", spec_p, "--stills"] + (["--beats", ",".join(only)] if only else [])
    run_blender(prefix, args, os.path.join(build, "blender.log"))
    W, H = spec["resolution"]
    ids = [b["id"] for b in spec["beats"] if os.path.exists(os.path.join(d, f"{b['id']}.png"))]
    if not ids:
        raise SystemExit("no stills rendered - see build/blender.log")
    cols = min(len(ids), 6 if H > W else 4)
    tw = 300 if H > W else 480
    inputs, filt = [], []
    for i, bid in enumerate(ids):
        inputs += ["-i", os.path.join(d, f"{bid}.png")]
        filt.append(f"[{i}:v]scale={tw}:-2,pad=iw+8:ih+8:4:4:color=0x222222[v{i}]")
    rows = (len(ids) + cols - 1) // cols
    th = int(tw * H / W) // 2 * 2 + 8
    layout = "|".join(f"{(i % cols) * (tw + 8)}_{(i // cols) * th}" for i in range(len(ids)))
    filt.append("".join(f"[v{i}]" for i in range(len(ids))) +
                f"xstack=inputs={len(ids)}:layout={layout}:fill=0x111111[out]" if len(ids) > 1 else "[v0]null[out]")
    sheet = os.path.join(d, "contact_sheet.png")
    sh(["ffmpeg", "-y", "-v", "error"] + inputs + ["-filter_complex", ";".join(filt), "-map", "[out]",
                                                   "-frames:v", "1", sheet])
    log(f"stills: {d}  ({len(ids)} beats, {rows} row(s))")
    log(f"contact sheet: {sheet}  (order: {', '.join(ids)})")


def do_assemble(sb, spec, build, timeline, out_path):
    W, H = spec["resolution"]
    fps = spec["fps"]
    seg_dir = os.path.join(build, "segments")
    os.makedirs(seg_dir, exist_ok=True)
    concat_v, concat_a = [], []
    for b, tl, src in zip(spec["beats"], timeline, sb["beats"]):
        fr_dir = os.path.join(build, "frames", b["id"])
        if not beat_done(build, b):
            raise SystemExit(f"beat {b['id']} not rendered (or stale) - run the render stage first")
        seg = os.path.join(seg_dir, f"{b['id']}.mp4")
        dur = tl["duration"]
        vf = [f"scale={W}:{H}:flags=lanczos", "format=yuv420p"]
        tr = src.get("transition", sb.get("transition", "cut"))
        if tr == "fade":
            vf.insert(1, f"fade=t=in:st=0:d=0.2,fade=t=out:st={max(0, dur - 0.2):.3f}:d=0.2")
        sh(["ffmpeg", "-y", "-v", "error", "-framerate", str(fps), "-i", os.path.join(fr_dir, "%04d.png"),
            "-vf", ",".join(vf), "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
            "-r", str(fps), seg])
        concat_v.append(seg)
        aw = os.path.join(build, "audio", f"{b['id']}.wav")
        apad = os.path.join(seg_dir, f"{b['id']}.wav")
        if tl["speech"] > 0 and os.path.exists(aw):
            ms = int(tl["lead"] * 1000)
            sh(["ffmpeg", "-y", "-v", "error", "-i", aw, "-af",
                f"adelay={ms}|{ms},apad=whole_dur={dur:.3f},atrim=0:{dur:.3f}", "-ar", "48000", "-ac", "1", apad])
        else:
            sh(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
                "-t", f"{dur:.3f}", apad])
        concat_a.append(apad)
    for lst, items in (("v.txt", concat_v), ("a.txt", concat_a)):
        with open(os.path.join(seg_dir, lst), "w") as f:
            f.writelines(f"file '{os.path.abspath(p)}'\n" for p in items)
    video = os.path.join(build, "video_silent.mp4")
    voice = os.path.join(build, "narration.wav")
    sh(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", os.path.join(seg_dir, "v.txt"),
        "-c", "copy", video])
    sh(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", os.path.join(seg_dir, "a.txt"),
        "-c", "pcm_s16le", voice])
    total = sum(t["duration"] for t in timeline)

    # captions
    cap = sb.get("captions") or {}
    ass_p = os.path.join(build, "captions.ass")
    srt_p = os.path.splitext(out_path)[0] + ".srt"
    hi = STYLES.get(sb["style"], {}).get("caption_highlight", "#FFE600")
    ass, srt = captions.build([t["words"] for t in timeline], W, H, cap, hi)
    open(ass_p, "w").write(ass)
    open(srt_p, "w").write(srt)

    # audio mix: narration (+ music ducked under it) -> loudness normalised
    music = (sb.get("music") or {})
    inputs = ["-i", video, "-i", voice]
    if music.get("file") and os.path.exists(music["file"]):
        inputs += ["-stream_loop", "-1", "-i", music["file"]]
        vol = float(music.get("volume", 0.18))
        fo = max(0.0, total - 2.0)
        afilt = (f"[2:a]volume={vol},afade=t=in:d=1.0,afade=t=out:st={fo:.2f}:d=2.0,atrim=0:{total:.3f}[m];"
                 f"[1:a]asplit=2[v1][v2];[m][v2]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=350[md];"
                 f"[v1][md]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    else:
        if music.get("file"):
            log(f"music file not found, skipping: {music['file']}")
        afilt = "[1:a]loudnorm=I=-14:TP=-1.5:LRA=11[a]"
    vfilt = "[0:v]null[v]"
    if cap.get("enabled", True):
        fdir = cap.get("fonts_dir") or os.path.join(os.path.dirname(HERE), "assets", "fonts")
        esc = lambda p: p.replace("\\", "/").replace(":", r"\:").replace("'", r"\'")  # noqa: E731
        fd = f":fontsdir='{esc(fdir)}'" if os.path.isdir(fdir) else ""
        vfilt = f"[0:v]ass='{esc(ass_p)}'{fd}[v]"
    sh(["ffmpeg", "-y", "-v", "error"] + inputs + [
        "-filter_complex", f"{vfilt};{afilt}", "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(fps),
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{total:.3f}", "-movflags", "+faststart", out_path])

    # thumbnail from the beat flagged "thumbnail": true (default: first beat), no captions
    tb = next((i for i, b in enumerate(sb["beats"]) if b.get("thumbnail")), 0)
    tt = timeline[tb]["start"] + timeline[tb]["duration"] * 0.7
    thumb = os.path.splitext(out_path)[0] + "_thumb.jpg"
    sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{tt:.2f}", "-i", video, "-frames:v", "1", "-q:v", "2", thumb])

    md = sb.get("metadata") or {}
    if md:
        mp = os.path.splitext(out_path)[0] + "_upload.md"
        with open(mp, "w") as f:
            f.write(f"# {md.get('title', sb.get('title', ''))}\n\n{md.get('description', '')}\n\n")
            if md.get("tags"):
                f.write("**Tags:** " + ", ".join(md["tags"]) + "\n\n")
            if md.get("hashtags"):
                f.write(" ".join("#" + x.lstrip("#") for x in md["hashtags"]) + "\n")
    log(f"DONE -> {out_path}  ({total:.1f}s, {W}x{H}@{fps})")
    log(f"also: {thumb}, {srt_p}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("storyboard")
    ap.add_argument("--stage", default="all", choices=["all", "validate", "tts", "stills", "render", "assemble"])
    ap.add_argument("--quality", default=None, choices=["draft", "standard", "high"])
    ap.add_argument("--engine", default=None, choices=["auto", "eevee", "cycles", "workbench"])
    ap.add_argument("--beats", default="", help="comma separated beat ids to (re)process")
    ap.add_argument("--force", action="store_true", help="ignore caches")
    ap.add_argument("--blender", default=None, help="path to blender executable (or python with bpy)")
    ap.add_argument("--save-blend", action="store_true", help="save a .blend per beat to tweak by hand")
    ap.add_argument("--out", default=None, help="output mp4 path")
    a = ap.parse_args()

    sb = load(a.storyboard)
    root = os.path.dirname(os.path.abspath(a.storyboard))
    os.chdir(root)  # relative asset paths in the storyboard resolve from its folder
    build = os.path.join(root, "build")
    os.makedirs(build, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", sb.get("title", "video").lower()).strip("-") or "video"
    quality = a.quality or (sb.get("render") or {}).get("quality", "standard")
    out = a.out or os.path.join(root, f"{slug}{'_draft' if quality == 'draft' else ''}.mp4")
    only = [x for x in a.beats.split(",") if x] or None

    probs, est = validate(sb)
    for p in probs:
        log("WARN", p)
    log(f"{len(sb['beats'])} beats, estimated length ~{est:.0f}s, format={sb['format']}, style={sb['style']}")
    if a.stage == "validate":
        sys.exit(1 if any("unknown" in p or "not found" in p for p in probs) else 0)

    timeline = do_tts(sb, build, a.force, only)
    if a.stage == "tts":
        return
    prefix = find_blender(a.blender)
    if a.stage in ("all", "stills", "render") and not prefix:
        raise SystemExit("Blender not found. Install Blender 4.2+ and put it on PATH, set BLENDER=/path/to/blender, "
                         "or `pip install bpy` (Python version must match the bpy wheel).")
    engine = a.engine or (sb.get("render") or {}).get("engine", "auto")
    if prefix and a.stage != "assemble":
        engine = pick_engine(prefix, engine, build)
    elif engine == "auto":
        engine = open(os.path.join(build, "engine.txt")).read().strip() \
            if os.path.exists(os.path.join(build, "engine.txt")) else "cycles"
    spec, spec_p = render_spec(sb, build, timeline, engine, quality)
    if a.stage == "stills":
        do_stills(prefix, spec, spec_p, build, only)
        return
    if a.stage in ("all", "render"):
        do_render(prefix, spec, spec_p, build, only, a.force, a.save_blend)
    if a.stage in ("all", "assemble"):
        do_assemble(sb, spec, build, timeline, out)


if __name__ == "__main__":
    main()

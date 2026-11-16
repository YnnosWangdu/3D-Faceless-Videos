#!/usr/bin/env python3
"""Check everything the faceless-video kit needs and say how to fix what's missing.

    python check_env.py            # report
    python check_env.py --probe    # also test-render one tiny frame to see if EEVEE works
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tts  # noqa: E402
from make_video import find_blender, pick_engine  # noqa: E402

OK, BAD, MEH = "✅", "❌", "⚠️"


def main():
    probe = "--probe" in sys.argv
    hard_fail = False
    print("Faceless 3D video kit - environment check\n")
    ff = shutil.which("ffmpeg")
    if ff:
        filters = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        has_ass = " ass " in filters
        print(f"{OK if has_ass else MEH} ffmpeg: {ff}" + ("" if has_ass else "  (no libass: captions can't be burned in; "
                                                         "install a full ffmpeg build)"))
    else:
        hard_fail = True
        print(f"{BAD} ffmpeg missing -> macOS: brew install ffmpeg | Ubuntu: sudo apt install ffmpeg | "
              "Windows: winget install Gyan.FFmpeg")
    print(f"{OK if shutil.which('ffprobe') else BAD} ffprobe")

    pre = find_blender()
    if pre:
        if len(pre) == 1:
            v = subprocess.run(pre + ["-c", "import bpy;print(bpy.app.version_string)"], capture_output=True,
                               text=True).stdout.strip().splitlines()[-1:]
            print(f"{OK} Blender via bpy module ({pre[0]}) version {v[0] if v else '?'}")
        else:
            v = subprocess.run([pre[0], "-b", "--version"], capture_output=True, text=True).stdout.splitlines()
            print(f"{OK} Blender: {pre[0]}  {v[0] if v else ''}")
        if probe:
            d = tempfile.mkdtemp()
            eng = pick_engine(pre, "auto", d)
            print(f"   render engine that works here: {eng}"
                  + ("" if eng == "eevee" else "  (EEVEE needs a GPU/display; Cycles CPU is ~10-30x slower)"))
    else:
        hard_fail = True
        print(f"{BAD} Blender not found -> install 4.2 LTS or newer from blender.org and put it on PATH, "
              "or set BLENDER=/path/to/blender (macOS: /Applications/Blender.app/Contents/MacOS/Blender)")

    print("\nVoice backends (first available is used with backend=auto):")
    for k, v in tts.available().items():
        print(f"  {OK if v else '  '} {k:<11} {v or ''}")
    if not tts.available().get("edge"):
        print(f"  {MEH} recommended free voice: pip install edge-tts")

    fonts = os.path.join(os.path.dirname(HERE), "assets", "fonts")
    have = [f for f in os.listdir(fonts) if f.lower().endswith((".ttf", ".otf"))] if os.path.isdir(fonts) else []
    print(f"\n{OK if have else MEH} caption/3D fonts in assets/fonts: {', '.join(have) or 'none (system fallback used)'}")
    styles = [k for k in json.load(open(os.path.join(HERE, 'blender', 'fv', 'styles.json'))) if k != '_doc']
    print(f"   styles: {', '.join(styles)}")
    print("\n" + ("Not ready - fix the items marked " + BAD if hard_fail else "Ready to make videos."))
    sys.exit(1 if hard_fail else 0)


if __name__ == "__main__":
    main()

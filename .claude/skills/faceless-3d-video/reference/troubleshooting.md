# Troubleshooting

| symptom | fix |
|---|---|
| `Blender not found` | Install Blender 4.2 LTS or newer, then add it to PATH or `export BLENDER=/path/to/blender`. macOS: `/Applications/Blender.app/Contents/MacOS/Blender`. Windows: `C:\Program Files\Blender Foundation\Blender 4.x\blender.exe`. Alternative: `pip install bpy`, but the Python version must match the wheel. |
| "EEVEE unavailable → Cycles" | EEVEE needs a GPU and a display (or EGL). On headless servers use Cycles: `--quality draft` while iterating, `fps: 24`, and fewer beats. Delete `build/engine.txt` to re-probe after a driver install. |
| Render is very slow | Try, in order: `--quality draft`, `fps: 24`, `--engine eevee` on a GPU machine, fewer `glass` materials, and `"background": "none"`. A Cycles GPU (CUDA/OptiX/HIP/Metal) is picked up automatically. |
| A beat failed | Read the traceback in `build/blender.log`. It's usually a bad param type (a string where a number belongs) or a missing image path. |
| Text overlaps or is cut off | Shorten the text, lower `size`, or switch to a template with more room. Then check with `--stage stills --beats id`. |
| Captions cover the 3D content | Set `captions.position` to `bottom` or `top`, or `captions.words_per_line: 2`. |
| Caption font looks wrong | Copy a `.ttf` into `.claude/skills/faceless-3d-video/assets/fonts/` and set `captions.font` to the font's *family name* (`fc-scan file.ttf` shows it). |
| `edge-tts` errors | It needs internet. Update it with `pip install -U edge-tts`. List voices with `edge-tts --list-voices`. Offline, use `piper` with a downloaded voice, `say` (macOS) or `espeak`. |
| Voice says numbers or acronyms wrong | Spell them out in `narration` ("N. A. S. A." or "nasa"). |
| Captions drift from the voice | Backends without native timings (openai, piper, say, your own audio) use estimated timings. Install `faster-whisper` and set `captions.align: "whisper"`. |
| Changed one beat but everything re-rendered | Changing narration length shifts the beat's duration, which re-renders that beat only. A global change (style, format, fps, quality, font) re-renders all beats, as intended. |
| Video looks too dark or flat | Try another `style`, raise `glow`, or use `style_overrides` to brighten `bg_top`. Light styles (pastel, clay) suit bright topics. |
| Want to hand-tweak a scene | Use `--save-blend`, open `build/blend/<id>.blend` in Blender, edit, and render the frames into `build/frames/<id>/`. Keep the `.done` file, then run `--stage assemble`. |

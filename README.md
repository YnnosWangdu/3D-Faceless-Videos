# 3D Faceless Videos: a Claude Code + Blender kit

Tell Claude Code *"make me a 45-second short about why the ocean is so deep"* and get a finished
vertical MP4 back. It includes a neural voiceover, procedurally animated 3D scenes rendered in
Blender, word-by-word captions, ducked background music, a thumbnail and upload metadata. You never
show your face or open an editor.

```
topic ─▶ Claude writes script + storyboard.json
       ─▶ TTS voiceover per beat (word timings)
       ─▶ Blender renders a 3D scene per beat (14 templates × 8 styles, 9:16 / 16:9 / 1:1)
       ─▶ captions (.ass burned in + .srt) ─▶ ffmpeg mix, -14 LUFS ─▶ video.mp4 + thumb + upload.md
```

## Setup (once)

1. **Blender 4.2 LTS or newer** from [blender.org](https://www.blender.org/download/). Put it on
   PATH or set `BLENDER=/path/to/blender`.
   (Alternative: `pip install bpy` gives Blender as a Python module.)
2. **ffmpeg** (with libass, which standard builds include): `brew install ffmpeg`,
   `sudo apt install ffmpeg` or `winget install Gyan.FFmpeg`.
3. **Voice:** `pip install -r requirements.txt` installs edge-tts, which is free.
   ElevenLabs and OpenAI work too if you set `ELEVENLABS_API_KEY` or `OPENAI_API_KEY`.
4. Optional: put a bold `.ttf` (e.g. Montserrat Black) in
   `.claude/skills/faceless-3d-video/assets/fonts/`.
5. Check everything:
   ```bash
   python .claude/skills/faceless-3d-video/scripts/check_env.py --probe
   ```

A GPU is strongly recommended. With one, EEVEE renders a 45 s short in a few minutes. On CPU only,
the kit falls back to Cycles automatically and takes much longer.

## Use it with Claude Code

Open this folder in Claude Code and ask for what you want:

> Make a 40-second YouTube Short about the deepest point in the ocean, ocean style, punchy captions.

> Turn this script into a 16:9 explainer with the noir style: …

> Re-render the third beat as a bar chart and make the hook text bigger.

You can also invoke the skill directly with `/faceless-3d-video`. Claude will:
1. Write the script and `projects/<slug>/storyboard.json`.
2. Render **preview stills**, look at them, and fix layout problems.
3. Render a draft, then the final video.
4. Hand you `projects/<slug>/<slug>.mp4`, a thumbnail, an `.srt` file and `_upload.md`
   (title, description, tags).

## Use it by hand

```bash
KIT=.claude/skills/faceless-3d-video/scripts
cp -r .claude/skills/faceless-3d-video/examples/deep-ocean-short projects/
python $KIT/make_video.py projects/deep-ocean-short/storyboard.json --stage stills   # preview
python $KIT/make_video.py projects/deep-ocean-short/storyboard.json --quality draft  # fast draft
python $KIT/make_video.py projects/deep-ocean-short/storyboard.json                  # final
```

Everything is cached. Edit one beat and only that beat is re-voiced and re-rendered.

## What's in the box

| path | what |
|---|---|
| `.claude/skills/faceless-3d-video/SKILL.md` | the workflow Claude follows |
| `…/scripts/make_video.py` | pipeline: validate → tts → stills/render → assemble |
| `…/scripts/blender/render_beats.py` | Blender entry point (EEVEE / Cycles / Workbench, GPU auto-detect) |
| `…/scripts/blender/fv/templates.py` | 14 scene templates: title, quote, cta, hero, versus, image_card, bar_chart, counter, list, timeline, globe, abstract, landscape, city |
| `…/scripts/blender/fv/core.py` | 3D text and layout, materials, lights, cameras and animation helpers |
| `…/scripts/blender/fv/styles.json` | 8 looks: neon, space, noir, sunset, ocean, forest, pastel, clay |
| `…/scripts/tts.py` | voices: edge, elevenlabs, openai, piper, say, espeak, silent, or your own recordings |
| `…/scripts/captions.py` | pop, karaoke, clean and box caption styles |
| `…/reference/` | storyboard schema, template catalogue, script-writing guide, troubleshooting |
| `…/examples/` | a 9:16 short and a 16:9 explainer, ready to render |

## Licence notes

The code is yours to use. Only use music, fonts and images you have rights to. Platforms ask you to
disclose realistic AI-generated or synthetic content, so check the upload settings.

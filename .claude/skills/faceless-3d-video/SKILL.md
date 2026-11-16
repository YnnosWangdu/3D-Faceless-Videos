---
name: faceless-3d-video
description: Make complete faceless 3D videos (YouTube Shorts, TikTok, Reels or 16:9 explainers) with Blender. You write the script and storyboard, and the pipeline does neural voiceover, procedural 3D scenes (kinetic text, charts, counters, planets, cities, terrain, lists, timelines, product shots), word-timed captions, music ducking and the final MP4 with thumbnail and upload metadata. Use whenever the user wants a faceless, explainer, facts, top-N, story or "3D" video made, or wants to edit or re-render one made with this kit.
---

# Faceless 3D Video Kit

This skill turns a topic into a finished MP4. **You** write the script and pick the visuals in a
`storyboard.json`. The scripts handle the rest, and they cache their work so you can iterate cheaply:

```
storyboard.json ─▶ voiceover (per beat, word timings) ─▶ Blender renders one 3D scene per beat
               ─▶ captions (.ass/.srt) ─▶ ffmpeg: concat + music duck + loudnorm ─▶ final.mp4 + thumb + upload.md
```

Scripts live in `.claude/skills/faceless-3d-video/scripts/`. Below, `$KIT` means that directory.

## Workflow (follow in order)

1. **Check the environment once per machine:** `python $KIT/check_env.py --probe`.
   It needs Blender 4.2+ (or `pip install bpy`), ffmpeg, and for voice ideally `pip install edge-tts`.
   If something is missing, tell the user the exact install command it prints.
2. **Brief.** If the user hasn't said, choose sensible defaults and state them. Don't interrogate them.
   - Topic and angle, platform → `format` (`shorts` 9:16 is the default, or `landscape` 16:9, or `square`).
   - Length: Shorts run 30–60 s, which is 90–150 spoken words. Landscape explainers run 2–6 min.
   - `style`: neon, space, noir, sunset, ocean, forest, pastel or clay. Match it to the topic's mood.
   - Voice: `edge` is free and good. Use `elevenlabs` or `openai` if the user has keys. If the user
     has their own recordings, set `"audio"` per beat.
3. **Write the script** using `reference/script-writing.md` (hook in the first 2 s, one idea per beat,
   2–8 s per beat, a loop or CTA at the end). Check the facts. Don't invent statistics. If you aren't
   sure, say so or leave it out.
4. **Storyboard.** Create `projects/<slug>/storyboard.json`, using the schema in
   `reference/storyboard-schema.md` and choosing templates from `reference/scene-templates.md`.
   Vary the templates. Never use the same template twice in a row, and use data templates
   (bar_chart, counter, versus, timeline) whenever a number or comparison is spoken.
   `examples/` holds complete storyboards you can copy.
5. **Validate:** `python $KIT/make_video.py projects/<slug>/storyboard.json --stage validate`.
   Fix every WARN.
6. **Preview stills (always do this before a full render):**
   `python $KIT/make_video.py projects/<slug>/storyboard.json --stage stills`, then **Read**
   `projects/<slug>/build/stills/contact_sheet.png`, plus individual stills if needed. Check for
   overlapping or cut-off text, empty frames, unreadable contrast, and captions colliding with content.
   Fix the storyboard (shorter text, other template or params, `size`, `style_overrides`) and re-run
   stills for just those beats with `--beats id1,id2`.
7. **Draft video** (half resolution, fast): `... --quality draft`. Re-render single beats with `--beats`.
8. **Final:** `... --quality standard` (or `high` for motion blur and more samples). Render times:
   EEVEE on a GPU takes about 0.2–1 s/frame. Cycles on a CPU takes about 2–10 s/frame, roughly
   30–90 min for a 45 s short. In that case, warn the user, run it in the background, and suggest
   `fps: 24`.
9. **Deliver:** `projects/<slug>/<slug>.mp4`, `<slug>_thumb.jpg`, `<slug>.srt` and `<slug>_upload.md`
   (title, description, tags, taken from `metadata`). Give the paths and the total duration.

## Commands

```bash
python $KIT/make_video.py SB.json                    # full pipeline (cached)
python $KIT/make_video.py SB.json --stage validate   # lint + estimated length
python $KIT/make_video.py SB.json --stage tts        # voice only -> build/timeline.json (real durations)
python $KIT/make_video.py SB.json --stage stills     # preview frames + contact sheet
python $KIT/make_video.py SB.json --stage render     # frames only
python $KIT/make_video.py SB.json --stage assemble   # re-mux (after caption/music edits, no re-render)
  --quality draft|standard|high   --engine auto|eevee|cycles|workbench
  --beats id1,id2   --force   --blender /path/to/blender   --save-blend   --out file.mp4
```

`--save-blend` writes `build/blend/<beat>.blend` so the user can open and tweak a scene in Blender.

## Editing rules

- Changing a beat's `narration` re-voices only that beat and shifts later timings. Captions and
  audio always follow, but beats whose duration changed get re-rendered.
- Changing `scene` re-renders only that beat. Changes to `captions`, `music` or `metadata` need
  only `--stage assemble`.
- Text inside 3D scenes should be short: 2–7 words for a `title`, 1–4 words per list item or label.
  The narration carries the detail, and the captions show it word for word.
- In 3D text, wrap words in `*asterisks*` to colour them with the accent colour.
- Want a look the templates don't have? Add a template. See "Extending" in
  `reference/scene-templates.md`. Templates are plain Blender Python in `scripts/blender/fv/templates.py`.

## Troubleshooting

See `reference/troubleshooting.md`. Quick hits:
- The renderer falls back to Cycles. That means EEVEE couldn't start (no GPU or display), which is
  normal on servers. Use `--quality draft` while iterating.
- Captions burn with the wrong font: put a `.ttf` in `$KIT/../assets/fonts/` and set
  `captions.font` to its family name.
- `blender.log` in `build/` has the full Blender output for any failed beat.

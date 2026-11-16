# storyboard.json schema

Paths are relative to the storyboard's folder. Everything except `beats` is optional.

```jsonc
{
  "title": "How Deep Is The Ocean",          // also the output file name (slugified)
  "format": "shorts",                         // shorts|vertical|reels|tiktok (1080x1920), landscape|youtube (1920x1080), square, 4k
  "resolution": [1080, 1920],                 // overrides format
  "style": "neon",                            // neon space noir sunset ocean forest pastel clay
  "style_overrides": { "accent": "#FF0055" }, // any key from scripts/blender/fv/styles.json
  "fps": 30,                                  // 24 renders 20% faster and looks filmic
  "font": "assets/fonts/Anton-Regular.ttf",   // font for 3D text (default: Blender's built-in)
  "lead": 0.12,                               // silence before each beat's narration (s)
  "pad": 0.35,                                // silence after each beat's narration (s)
  "transition": "cut",                        // cut | fade (per beat override allowed)

  "voice": {
    "backend": "auto",                        // auto edge elevenlabs openai piper say espeak silent
    "voice": "en-US-AndrewMultilingualNeural",// edge voice / elevenlabs voice_id / openai voice / say voice
    "rate": "+8%",                            // edge only: speaking speed
    "pitch": "+0Hz",                          // edge only
    "model": "eleven_multilingual_v2",        // elevenlabs/openai model, or piper .onnx path
    "instructions": "Calm documentary tone"   // openai gpt-4o-mini-tts only
  },

  "captions": {
    "enabled": true,
    "style": "pop",                           // pop karaoke clean box
    "words_per_line": 3,                      // default 3 in 9:16, 6 in 16:9
    "max_chars": 18,
    "position": "lower",                      // lower (default 9:16) | bottom (default 16:9) | center | top
    "font": "Montserrat Black",               // family name; put the ttf in assets/fonts/
    "size": 0,                                // px, 0 = auto
    "uppercase": true,
    "color": "#FFFFFF",
    "highlight": "#FFE600",                   // default: style's caption_highlight
    "align": "whisper"                        // optional exact timings via faster-whisper (pip install faster-whisper)
  },

  "music": { "file": "assets/music/track.mp3", "volume": 0.18 },  // looped, faded, ducked under voice

  "render": { "engine": "auto", "quality": "standard" },          // CLI flags override

  "metadata": {                               // -> <slug>_upload.md
    "title": "…", "description": "…", "tags": ["…"], "hashtags": ["shorts"]
  },

  "beats": [
    {
      "id": "hook",                           // unique, [A-Za-z0-9_-]
      "narration": "Spoken text for this beat.",
      "scene": { "template": "title", "text": "Short *on-screen* text" },
      // optional:
      "audio": "rec/hook.wav",                // your own recording instead of TTS
      "duration": 3.0,                        // for beats without narration
      "min_duration": 2.5,                    // hold the visual longer than the speech
      "lead": 0.0, "pad": 0.6,                // per-beat overrides
      "transition": "fade",
      "thumbnail": true,                      // use this beat for the thumbnail
      "seed": 7                               // re-roll random layout (background shapes, city)
    }
  ]
}
```

## Scene params common to most templates

| key | meaning |
|---|---|
| `template` | see `scene-templates.md` |
| `camera` | `push` (slow dolly in), `pull`, `orbit`, `drift` (sideways), `crane` (rise), `static` |
| `background` | `shapes`, `stars`, `both` or `none` |
| `shape_count`, `star_count` | density of background props |
| `glow` | multiplier on the style's bloom (0 = off) |
| `still_at` | where in the beat (0–1) the preview still is taken (default 0.6) |
| `style_overrides` | colour overrides for this beat only |
| `color` | a hex value or a style key (`primary`, `secondary`, `accent`) |

## Timing

A beat lasts `lead + speech + pad`, at least 1 s. Animations inside a template are scheduled as
fractions of the beat, so they stretch to fit automatically. For lists and timelines, `reveal_at`
lets you line each item up with the moment it is spoken. Run `--stage tts`, look at the word times
in `build/timeline.json`, and set `reveal_at` to `(word_start - beat_start) / beat_duration`.

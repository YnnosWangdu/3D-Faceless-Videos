# Scene templates

Every beat's `scene.template` picks one of these. All of them work in 9:16, 16:9 and 1:1, and they
adapt to all eight styles. Aliases are listed in brackets.

| template | use it for | key params |
|---|---|---|
| **title** [title_card, kinetic_text, hook, statement] | hooks, claims, punchlines. 3D words pop in one by one | `text` (`*word*` = accent), `subtitle`, `size`, `anim` pop/slide/drop/none, `stagger` |
| **quote** | quotes, definitions, "they said…" | `text`, `author` |
| **cta** [outro, subscribe] | the last beat: follow/subscribe | `text`, `subtitle` |
| **hero** [hero_object, object, product] | "this thing": a gem, a coin, a planet-like orb, a product stand-in | `object`, `material`, `color`, `label`, `caption`, `pedestal`, `orbit` (deg), `turns` |
| **versus** [comparison, vs] | A vs B, before/after, cheap vs expensive | `left`/`right`: `{label, object, material, color, value, prefix, suffix}`, `title`, `vs_text` |
| **image_card** [image, photo] | real photos, AI art, screenshots, maps, diagrams | `image` or `images` (up to 3, fanned), `caption` |
| **bar_chart** [bars, chart] | comparing 2–8 numbers | `bars: [{label, value, color?}]`, `title`, `prefix`, `suffix`, `decimals`, `grow_until` |
| **counter** [number, stat, big_number] | one dramatic number | `to`, `from`, `decimals`, `prefix`, `suffix`, `label`, `count_until` |
| **list** [list_reveal, steps, top_list] | top-N, steps, reasons | `items` (2–6 short strings), `title`, `reveal_at`, `numbered` |
| **timeline** | history, eras, sequences (vertical in 9:16) | `events: [{label, sub}]` (2–6), `title`, `reveal_at` |
| **globe** [planet, world] | geography, space, "the whole world…" | `planet` earth/mars/ice/lava/gas/alien/moon, `rings`, `atmosphere`, `label`, `caption`, `turns` |
| **abstract** [abstract_field, shapes, tunnel] | transitions, mystery, "what if…", filler between facts | `text`, `count`, `kinds`, `camera_speed` |
| **landscape** [terrain, flyover] | nature, history, travel, "imagine a valley…" | `biome` green/desert/snow/alien/volcanic, `text`, `caption`, `height`, `noise_scale` |
| **city** [skyline, cityscape] | economy, tech, urban, future, crime | `text`, `caption`, `density`, `camera_speed` |

**Objects** (hero, versus): sphere, cube, torus, cone, cylinder, icosphere, monkey, gem, crystal,
ring, coin, capsule, pyramid.
**Materials:** glossy, metal, gold, chrome, glass, neon, clay/matte, emissive.

## Choosing visuals: rules of thumb

- **Beat 1** is always `title` (or `counter` or `versus` when the hook is a number or comparison).
  Use big words and few of them.
- Whenever a number is spoken, show it: `counter` for one number, `bar_chart` or `versus` for two or more.
- Never use the same template twice in a row. Alternate dense beats (list, chart) with breathers
  (abstract, landscape, globe).
- Keep on-screen text short. Captions already show the narration, so 3D text should **summarise**,
  not repeat.
- For named real-world things (a person, a landmark, a product), use `image_card` with an image the
  user supplies or one they have rights to. Don't fake likenesses in 3D.
- In 9:16, captions sit in the lower third (`position: lower`) and templates keep content in the
  upper-middle. If a scene needs the full frame, set `captions.position: "top"` or `"bottom"`.

## Extending: add your own template

Templates are plain Blender Python functions in `scripts/blender/fv/templates.py`:

```python
@template("my_scene", "alias")
def t_my_scene(ctx, p):
    """One-line description. params: foo, bar."""
    background(ctx, p)                                   # world gradient + optional props
    light_rig(ctx, (0, 0, ctx.cz))                       # key / rim / fill lights
    cam, _ = camera(ctx, p.get("camera", "push"), target=(0, 0, ctx.cz))
    o = prim("torus", size=ctx.u, loc=(0, 0, ctx.cz), mat=mat_preset(ctx, "neon", ctx.style["accent"]))
    pop_in(o, ctx.f(0.05)); spin(o, ctx.frames, turns=0.5)
    hud(ctx, cam, p.get("label", ""), hud_top(ctx), ctx.u * 0.6)   # screen-locked title
```

Useful values on `ctx`:
- `ctx.frames` and `ctx.fps`. `ctx.f(0.5)` gives the frame halfway through the beat.
- `ctx.vw`/`ctx.vh`: the visible size at the y=0 plane. `ctx.cw`/`ctx.ch`/`ctx.cz`: the content box,
  which stays clear of captions. `ctx.u`: the layout unit.
- `ctx.style`: the palette. `ctx.dark`: whether the style is dark. `ctx.rng`: a seeded random generator.

Helpers in `fv/core.py`:
- Building: `text`, `word_block`, `hud`, `prim`, `floor`, `starfield`, `ambient_shapes`,
  `mat_principled`, `mat_emission`, `mat_preset`.
- Animation: `key`, `key_idx`, `pop_in`, `pop_out`, `slide_in`, `spin`, `wobble`, `show_between`.

The camera looks along +Y at the XZ plane, so text stands upright facing it. Validate with
`--stage stills --beats <id>`.

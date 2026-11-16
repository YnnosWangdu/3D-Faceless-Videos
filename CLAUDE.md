# 3D Faceless Videos

This repo is a Claude Code kit for making faceless 3D videos with Blender.

- The skill is `.claude/skills/faceless-3d-video/SKILL.md`. Follow its workflow for any video request.
- Each video lives in `projects/<slug>/storyboard.json`. Outputs (mp4, thumbnail, srt, upload notes) go
  next to the storyboard, and the cache goes in `projects/<slug>/build/`, which is gitignored.
- Always render `--stage stills` and look at `build/stills/contact_sheet.png` before a full render.
- Don't commit renders, music or fonts unless the user asks.

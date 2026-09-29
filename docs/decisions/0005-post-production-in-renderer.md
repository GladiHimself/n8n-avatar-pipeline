# 0005 — Post-production runs in the renderer sidecar, not in n8n

**Status:** accepted · Day 9

## Context
Day 9 needs FFmpeg for captions, intro/outro cards and a music bed. The n8n
image doesn't ship FFmpeg, and n8n 2.x disables the Execute Command node by
default because it's a security risk (any workflow editor could run shell commands).

## Decision
Add a `/v1/edits` endpoint to the existing `renderer` container, using the same
async job shape as `/v3/videos` (submit → poll → download `video_url`).
n8n keeps the logic that belongs to the pipeline: it builds the caption cues
in a Code node and chooses the title, outro text and whether to use music. The
sidecar only does the heavy media work.

## Consequences
- n8n stays a stock image, and no shell access is enabled.
- The edit-video sub-workflow is a near copy of render-avatar, so there's one pattern to learn.
- Caption timing is estimated from character counts, not real word timings.
  Upgrade path: ElevenLabs `/with-timestamps` returns character timings.
- Music is optional: drop a licensed track at `assets/music/bed.mp3`.
  `*.mp3` is gitignored, so music is never committed.

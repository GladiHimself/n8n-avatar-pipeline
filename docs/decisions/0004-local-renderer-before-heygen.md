# 0004 — Local renderer stands in for HeyGen until the client funds it

**Status:** accepted · Day 8

## Context
HeyGen stopped giving free API credits in Feb 2026. The API is pay-as-you-go
(from $5; Avatar III ≈ $0.99 per rendered minute). The build is free-tier first.

## Decision
Run a small sidecar (`services/renderer`) that copies HeyGen's `/v3/videos`
request and response shape. It uses FFmpeg to render a still avatar image, or
a plain background, with an audio waveform over it. It does no lip sync.

## Consequences
- The n8n side (submit → wait → poll → switch → download) is the real
  production shape, so switching is config, not a rebuild.
- To switch: set `RENDER_BASE_URL=https://api.heygen.com`, change the Header
  Auth credential to the HeyGen key, set a real `AVATAR_ID`, and add one node
  that uploads the MP3 to `POST /v3/assets` and passes `audio_asset_id`,
  because HeyGen can't read our local `/files`.
- Demo videos until then show no presenter. Tell the client before any demo.

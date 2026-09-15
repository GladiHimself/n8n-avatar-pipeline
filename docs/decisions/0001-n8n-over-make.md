# 0001 — Use self-hosted n8n instead of Make

Status: Accepted
Date: 2026-09-15

## Context

The pipeline needs an orchestrator for a multi-step media workflow:
script generation, text-to-speech, avatar video rendering, FFmpeg
post-production, a human approval gate, and a YouTube upload.

Two stages — avatar rendering and video encoding — are long-running
asynchronous jobs. Each requires submitting a job, receiving an ID, and
polling for completion over several minutes. A single video can mean
dozens of poll requests.

The workflow also handles a real person's likeness and voice, which
makes where the media and credentials live a contractual question, not
just a technical one.

## Decision

Self-hosted n8n, running in Docker alongside Postgres.

Make and comparable hosted platforms bill per operation. Poll loops turn
that pricing model against us: the cost of a video scales with how long
its render happens to take, which is both unpredictable and unrelated to
the value produced. n8n's self-hosted edition has no per-operation
billing, so a slow render costs nothing extra.

Self-hosting also keeps the video files, the scripts and the API
credentials on infrastructure we control, and allows FFmpeg to run
locally against a mounted volume rather than shuttling large media
files through a third-party service.

## Consequences

Positive: no per-operation cost on poll loops; full control of media and
credentials; FFmpeg runs locally on mounted volumes; workflows export as
JSON and live in version control.

Negative: we own the hosting, the upgrades and the backups. Postgres and
the n8n data volume both need a backup story before handover. There is
no vendor support line.

Neutral: n8n's fair-code licence permits internal business use. If the
pipeline were ever resold as a hosted product, the licence terms would
need review.
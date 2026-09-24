# 0003 — ElevenLabs for text-to-speech

Status: Accepted
Date: 2026-09-24

## Context
The pipeline needs natural-sounding narration, and eventually the client's
own cloned voice. Voice is kept separate from the avatar step so the voice
and the face can be sourced and swapped independently, and so word-level
timing is available for captions.

## Decision
ElevenLabs via its HTTP API, called from a generate-voice sub-workflow. The
API key is stored as an n8n Header Auth credential; the voice ID is config
in .env (VOICE_ID). Audio is written to /files/audio and only the path is
passed between workflows.

## Consequences
The free plan (~10,000 credits/month, ~10 minutes of audio) is sufficient for
building and private testing only. It has no commercial licence and requires
attribution. Before any video is published on the client's channel, the
client must hold at least the Starter plan (~$5/month), which also enables
instant voice cloning.

A credit guard in generate-voice refuses narration over 1,500 characters to
prevent a runaway script from consuming the monthly allowance.

Fallback: local open-source TTS (e.g. Piper) — free and unrestricted, but
lower quality and no voice cloning.
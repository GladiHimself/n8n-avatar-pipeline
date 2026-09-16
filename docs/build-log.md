# Build log

## Day 1 — 2026-09-15
n8n + Postgres 16 running under Docker Compose. Encryption key pinned in
.env, healthcheck-gated startup so n8n waits for Postgres to accept
connections, Asia/Kolkata timezone set for Schedule triggers, ./files
mounted at /files for FFmpeg output later.

Covered the canvas, the item model (every connection carries an array of
items; nodes run once per item), expressions, and pinned data.

Google Cloud project `avatar-content-pipeline` created on a dedicated
project Google account. YouTube Data API v3 enabled, OAuth consent screen
configured with the youtube.upload and youtube.force-ssl scopes, OAuth
client `n8n-local` created with the n8n callback URI. YouTube channel
created. Audit answers prepared in docs/youtube-audit.md — submission
deferred until the first working upload, since the reviewer needs a
functioning integration to assess.

## Day 2 — 2026-09-16
script-generator workflow built and exported.

Basic LLM Chain with a Google Gemini Flash chat model (free tier) and a
Structured Output Parser enforcing the script schema: hook, body, cta,
title, description, tags, estimated_seconds. The parser validates the
model's response against a JSON example, so malformed output fails loudly
instead of flowing downstream as prose.

A Set node normalises the chain's wrapped output into eleven flat fields.
It also builds the `narration` block (hook + body + cta joined) that Day 7's
text-to-speech will read, derives a URL slug from the title, and appends
the AI-presenter disclosure to every description in the pipeline rather
than relying on the prompt to remember it.

Retry-on-fail enabled on the chain (3 tries, 5s backoff) for free-tier 429s.

Open items: the model defaults to US dollars because nothing in the prompt
sets a locale — add currency/region to the input contract once the client's
audience is confirmed. The Gemini model ID is a preview build and should be
pinned to a stable release, ideally via an env var, before handover.
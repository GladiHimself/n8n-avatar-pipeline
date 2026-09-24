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

## Day 3 — 2026-09-17
Content calendar. Google Sheet "Content Calendar" (tab: videos) is now the
pipeline's state table — one row per video, status column driving the state
machine (pending → script_ready → ... → published | failed).

script-generator reads the next pending row, takes one via a Limit node,
generates the script, and writes title, description, tags, narration, slug
and timestamp back to the same row by matching on row_number.

Sheets OAuth2 reuses the Day 1 OAuth client. drive.file turned out too narrow
for the document picker — needed drive.readonly alongside spreadsheets.

Zero matching rows produces an empty item array, downstream nodes skip, and
the run finishes green. Intended behaviour for the Day 14 schedule trigger.

## Day 4 — 2026-09-18
Async job pattern, built standalone as workflows/async-job-pattern.json
against a simulated render API so all three paths could be tested without
burning provider credits.

Submit → Wait → Poll → Switch on three outcomes (completed / failed /
processing) → loop back to Wait while attempts remain, else Stop and Error.
Attempt counter uses $runIndex. Poll interval and max attempts are tunables
in a single Job Config node.

Verified: success in 4 polls, immediate failure, and timeout at exactly
max_attempts (3 of 3, no off-by-one).

Gotcha: n8n stores an expression with a leading "=" in the JSON
("={{ ... }}"). The Switch rules were saved as literal text, so no rule
ever matched and the node routed to no output at all — a silent failure
with no error. Look for the fx badge on the field.

Day 8 replaces the two mock Code nodes with HTTP Requests against HeyGen.
The structure doesn't change. Check then whether HeyGen supports webhook
callbacks — if so, Wait switches to "On Webhook Call" and the loop goes away.

## Day 5 — 2026-09-21
Split the monolith. generate-script is now a sub-workflow with a declared
input contract (row_number, topic, audience, tone, target_seconds), opening
with a Validate Input step that throws on a missing/short topic or an
out-of-range target_seconds. pipeline (renamed from script-generator) is the
orchestrator: read next pending row → call generate-script → save.

Three layers of error handling:
1. Retry — Retry On Fail on the LLM chain for transient 429s.
2. Handle — Generate Script uses "Continue (using error output)"; failures
   route to Mark Failed, which sets status=failed and writes the reason to
   the row. The run stays green and moves on.
3. Alert — error-alert workflow (Error Trigger → append to the errors tab)
   set as the Error Workflow for pipeline and generate-script.

Error workflows don't fire on manual executions. error-alert was tested with
pinned sample data; it fires for real once the schedule trigger is live.

## Day 6 — 2026-09-23
Week 1 milestone. Topic in → structured script out → written back to the
row, with bad input failing on its own row and the rest of the batch
continuing.

Cleared accumulated debts: deleted the Day 1 sandbox workflow; stripped
n8n's "[line N]" suffix from the error written to the sheet; enabled
Retry On Fail on all Google Sheets nodes; added a `region` field through
the whole contract (sheet column → Execute Workflow mapping → sub-workflow
input → prompt) so scripts use the right currency and examples instead of
defaulting to dollars; raised the batch limit from 1 to 3.

Documentation started while the decisions are fresh: architecture.md,
runbook.md, and ADR 0002 on using Sheets as the state store.

Verified a container restart preserves workflows, credentials and login.

## Day 7 — 2026-09-24
Voice. generate-voice sub-workflow: Input (row_number, slug, narration) →
Validate Narration (length and credit guard) → ElevenLabs TTS via HTTP
Request with Response Format: File → write MP3 to /files/audio → return the
path and character count, not the binary.

Pipeline now takes a row pending → script_ready → voiced in one run. Voice
failures reuse the existing Mark Failed node.

Compose: binary data mode set to filesystem, file access restricted to
/files, env access enabled in expressions so VOICE_ID can be read from .env.

Cost: ElevenLabs free plan is non-commercial. Client needs Starter (~$5/mo)
before publishing. See ADR 0003.
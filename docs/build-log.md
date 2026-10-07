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

## Day 8 — 2026-09-26
Avatar render. HeyGen stopped giving free API credits in Feb 2026 (now
pay-as-you-go from $5; Avatar III ≈ $0.99 per rendered minute), so a local
`renderer` sidecar (Python + FFmpeg) stands in with the same /v3/videos
request and response shape. Output is a still background with an audio
waveform and no lip sync. See ADR 0004.

render-avatar sub-workflow: Input (row_number, slug, audio_path) → Validate
Audio → Render Config → Submit Render (Header Auth + Idempotency-Key) →
Wait → Check Status → Switch (done / failed / fallback) → Attempts Left? →
loop back to Wait, or Stop and Error. On done: download video_url as a
File → write MP4 to /files/video → return path, render_id and duration.
This is the Day 4 async pattern with real HTTP calls.

Pipeline now takes a row pending → script_ready → voiced → rendered in one
run. Sheet gained video_path, render_id and video_seconds. Render failures
reuse Mark Failed.

Compose: third service `renderer` on the internal network (reached as
renderer:8080, not localhost), RENDER_BASE_URL and RENDERER_API_KEY in .env.
Switching to HeyGen later means changing the base URL, the credential, a
real AVATAR_ID, and adding one upload step to /v3/assets.

Snags: the credential title went into the Header Auth "Name" field, which
must be the header name (X-Api-Key). Leftover text in expression fields
broke the Wait amount and turned max_attempts into the string "300". A
Switch rule without the fx badge sent `failed` to Fallback, so the loop
polled until timeout. The VS Code preview plays MP4s without audio (no AAC
support), so check videos in QuickTime.

## Day 9 — 2026-09-29
Post-production. n8n 2.x disables the Execute Command node by default and
the image has no FFmpeg, so editing is a second endpoint, /v1/edits, on the
same renderer sidecar, using the same async job shape. See ADR 0005.

edit-video sub-workflow, duplicated from render-avatar: Input (row_number,
slug, video_path, title, narration, cta, video_seconds) → Build Captions
(Code: 5-word cues, timing estimated from character count) → Edit Config →
Submit Edit → poll loop → download → write MP4 to /files/final → return
final_path, final_seconds, caption count and music used.

The finished video is a 1.5s title card → narration with burned-in
captions → 2s outro card with the CTA. An optional music bed
(assets/music/bed.mp3, at 12% volume, gitignored) plays underneath.

Pipeline now reaches `edited`. Sheet gained final_path and final_seconds.
Edit failures reuse Mark Failed.

Config: EDIT_BASE_URL is separate from RENDER_BASE_URL, so moving renders
to HeyGen won't break editing. The renderer image now installs
fonts-dejavu-core for captions and title cards.

Known limits: caption timing is estimated, not word-accurate (upgrade path:
ElevenLabs /with-timestamps). Music must be licensed; never commit it.

## Day 10 — 2026-09-30
Thumbnail and YouTube metadata. New prepare-publish sub-workflow:
Input (row_number, slug, topic, title, description, tags) → Thumbnail Copy
(Gemini chain + Structured Output Parser: 2–4 word thumbnail text + 3
hashtags) → Build Metadata (Code: title ≤100 chars, no < >, description
≤5000 with the AI disclosure guaranteed once, #Shorts first, tags kept under
the 500-character total) → Make Thumbnail → Save Thumbnail (PNG to
/files/thumbs) → Package Result.

Make Thumbnail calls a new synchronous /v1/thumbnails endpoint on the
renderer. The response body is the PNG (1280×720), so there's no submit/poll:
a job that finishes in under a second doesn't need the async pattern.

Pipeline now reaches `packaged`. Sheet gained yt_title, yt_description,
yt_tags, thumbnail_text and thumbnail_path. The YouTube channel was
phone-verified so it can set custom thumbnails.

Snags: the Save Thumbnail node was missing, so the run was green but no file
was written. `$json` used in a "Run Once for All Items" Code node (use
`$input.first().json`). The Input `tags` field was typed String, not Array;
pinned data skipped the type check, so it only failed when the pipeline
called it. Gemini returned 503s, so Thumbnail Copy got retries and On Error →
Continue, and Build Metadata falls back to title-based text.

## Day 11 — 2026-10-02
Human approval gate over Telegram. New request-approval workflow, called
fire-and-forget (Wait For Sub-Workflow Completion OFF) so a slow human never
blocks the batch: Input → Read Video → Send Preview (Telegram video) → Mark
Awaiting (status awaiting_approval) → Send Review Link → Wait For Decision
(Wait node, On Form Submitted: decision dropdown approve / reject /
regenerate + notes, 24h limit) → Read Decision (Code) → Save Decision →
Confirm.

Decisions map to statuses: approve → approved, reject → rejected,
regenerate → pending, no answer in 24h → review_expired. Paused executions
are stored in Postgres and survive a container restart. request-approval is
the only sub-workflow with error-alert as its own Error Workflow, because the
caller doesn't wait and can't catch its errors.

Telegram bot created with BotFather. The token lives only in an n8n
credential, and TELEGRAM_CHAT_ID is in .env. Sheet gained review_decision,
review_notes and reviewed_at.

Snags: Telegram rejects localhost URLs on inline buttons ("Wrong HTTP
URL"), so Send and Wait for Response couldn't work. It was replaced with a
plain-text message carrying $execution.resumeFormUrl plus a Wait node form.
The link only opens on the Mac (copy it into the browser) until n8n has a
public URL. Typing "approve" in the chat does nothing; the decision goes
through the form.

## Day 12 — 2026-10-06
Stage resume. The pipeline is now a state machine driven by the sheet's
status column, so a failure late in the run no longer repeats paid work.

New advance-video sub-workflow, called once per row: Input (row_number) →
Load Row → This Row (filter) → Step Guard (If $runIndex < 8, else Too Many
Steps) → Stage Router (Switch on status) → exactly one stage → its Save node
→ back to Load Row. The routes are pending → script, script_ready → voice,
voiced → render, rendered → edit, edited → package, packaged → approval (end).
Every stage reads its inputs from the saved row, not from earlier nodes, so
a run can start at any stage. cta is now saved to the sheet for that reason.

Record Failure catches errors from every stage and writes status failed plus
failed_stage. To resume, copy failed_stage back into status.

pipeline slimmed to Manual Trigger → Read Calendar (all rows) → Actionable
(Filter: status in the actionable list) → Limit → Advance Video, with Mark
Failed as a backstop. Attempt To Convert Types is ON on every Execute
Workflow node, because Sheets values can arrive as strings.

Verified: a row at `edited` jumped straight to Prepare Publish, and script,
voice, render and edit were skipped.

Snags: the This Row filter used a String operator on numbers. Stage Router
rules had node names in the value field and needed fx on the left. A stray
comma in a mapping, and video_seconds mapped to description. Including
`approved` in Actionable before its route existed used up the Limit slots,
so the pending row was never reached. Repeated Gemini 503s on
gemini-3-flash-preview, so the plan is to move generate-script and
prepare-publish to a stable Flash model with 5 retries.

## Day 13 — 2026-10-07
YouTube upload. New publish-video sub-workflow, called by advance-video on
the `approved` route: Input (row_number, slug, final_path, thumbnail_path,
yt_title, yt_description, yt_tags) → Read Video → Upload Video (YouTube node,
privacy from YT_PRIVACY, not made for kids, retry 2 × 5000ms) → Make AI
content → Read Thumbnail → Set Thumbnail → Publish Result (row_number,
youtube_id, video_url as youtube.com/shorts/{id}, thumbnail_set,
published_at). Save Publish writes status published and loops back to Load
Row like every other stage.

Make AI content is an HTTP PUT to videos?part=status using the YouTube
OAuth2 credential (Predefined Credential Type). It sets
containsSyntheticMedia: true, the altered-content label. The PUT replaces
the whole status block, so privacyStatus and selfDeclaredMadeForKids are sent
again. Set Thumbnail is a binary POST to thumbnails/set with On Error →
Continue, so a failed thumbnail never blocks a published video. The AI
disclosure is still added in code to every description (Build Metadata,
Day 10).

The Google Cloud project hasn't been audited, so every API upload is forced
to private whatever the request says. YT_PRIVACY=private in .env makes that
explicit; switch it to public after the audit. Quota is about 100 units per
upload plus 50 per thumbnail. YouTube credential created via OAuth2 (same
Testing-mode app as Sheets, so tokens expire every 7 days until it is
published).

Day 12 had been skipped, so it was built mid-day. The Day 13 work in progress
(.env.example, docker-compose.yml) was committed on its own branch, Day 12 was
built on a fresh branch from main, and main gets merged back into the Day 13
branch.

Verified: a new row went pending → awaiting_approval → approved via the
Telegram form → published. Old approved rows published too: all private,
listed under the Shorts tab in Studio, with the disclosure in the
description, made-for-kids No and Altered content Yes.

Snags: Error Workflow lives in workflow Settings (⋯ → Settings), not node
settings. The YouTube node was named "Upload a video", and its output field
is uploadId, not id. The upload doesn't show under Videos; Shorts have their
own tab. Limit 3 picks actionable rows top-down, so old approved rows used
the slots and the new pending row waited for the next run. Row 4 had been
set to approved by hand with an empty final_path, and Read Video failed with
"Patterns must be a string (non empty)". Test rows with no files were
archived. Planned guards: a "Has Final File?" check before publish, and a
skip when youtube_id is already filled, so a row can't upload twice.

Open: submit the YouTube API audit with a demo screencast (note the date in
docs/youtube-audit.md), publish the OAuth app to Production, and switch the
Gemini nodes to a stable Flash model.
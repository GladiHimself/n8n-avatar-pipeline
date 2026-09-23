# Architecture

## Overview

An automated pipeline that turns a topic into a published YouTube video
featuring an AI presenter, with a human approval step before publishing.

    Google Sheet (state)
            │
            ▼
    pipeline (orchestrator)
            │
            ├──► generate-script  ──► script written back to the row
            ├──► generate-voice   (Day 7)
            ├──► render-avatar    (Day 8)
            ├──► post-production  (Day 9)
            ├──► approval gate    (Day 11)
            └──► publish          (Day 13)

## Components

**Content Calendar (Google Sheet)** — the state store. One row per video.
The `status` column is a state machine: pending → script_ready → voiced →
rendered → edited → awaiting_approval → approved → published, plus failed.
A second tab, `errors`, receives crash logs.

**pipeline** — the orchestrator. Reads the next pending rows, calls each
stage in order, writes results back to the row. Deliberately thin: it
sequences and persists, it does not do the work.

**generate-script** — sub-workflow. Contract: row_number, topic, audience,
tone, target_seconds, region. Validates input, calls Gemini Flash through a
Basic LLM Chain with a Structured Output Parser, and returns a flat object
containing hook, body, cta, title, description, tags, narration and slug.
The synthetic-media disclosure is appended to every description here, in
code, so it cannot be forgotten.

**async-job-pattern** — reference implementation of submit → wait → poll →
branch → give up, currently running against a mock. Days 8 and 9 build on it.

**error-alert** — error workflow. Logs uncaught failures to the errors tab.
Set as the Error Workflow on pipeline and generate-script.

## Error handling

Three layers:

1. Retry — Retry On Fail on every node that calls an external API, for
   transient failures (429s, network blips).
2. Handle — expected failures (bad input, provider rejection) flow out of a
   node's error output, mark that row failed with a reason, and let the run
   continue with the other rows.
3. Alert — anything uncaught fires the error workflow. Note that n8n does
   not run error workflows for manual executions, only automatic ones.

## Infrastructure

n8n and Postgres 16 in Docker Compose. Postgres holds workflows, encrypted
credentials and full execution history. Credentials are encrypted with
N8N_ENCRYPTION_KEY, which is pinned in .env and must be backed up — losing
it makes every stored credential unreadable.

## Accounts

All Google services run under a single project account, to be handed to the
client at the end. Cloud project avatar-content-pipeline hosts the YouTube
Data API and the OAuth client; the same OAuth client serves both Sheets and
(from Day 13) YouTube.
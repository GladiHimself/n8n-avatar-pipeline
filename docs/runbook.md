# Runbook

## Starting and stopping

    cd ~/n8n-avatar-pipeline
    docker compose up -d          # start
    docker compose ps             # check health
    docker compose down           # stop, keeps data
    docker compose down -v        # DESTROYS the database. Almost never.

n8n: http://localhost:5678

## A row is stuck

Look at its `status` column first — that tells you which stage it reached.

| status | meaning | next |
|---|---|---|
| pending | not picked up yet | run pipeline, or check for a trailing space in the cell |
| script_ready | script written | waiting for the voice stage (Day 7) |
| failed | a stage rejected it | read the `error` column |

To retry a failed row: fix whatever the `error` column names, clear that
cell, set status back to `pending`.

## Where to look

- n8n **Executions** tab (per workflow) — every past run with full data.
- Sub-workflows have their own Executions tab; a failure inside
  generate-script is visible there, not in pipeline.
- The `errors` sheet tab — uncaught crashes.
- `docker compose logs -f n8n` — only if n8n itself is misbehaving.

## Known failure modes

**"insufficient authentication scopes"** — the Google credential needs
reconnecting after a scope change.

**Auth fails after about a week** — the Google OAuth app is in Testing mode,
which expires refresh tokens after 7 days. Reconnect the credential. Must be
resolved before handover.

**429 from Gemini** — free-tier rate limit. Retry On Fail handles it; if it
persists, reduce the batch size.

**A run finishes green having done nothing** — no rows matched `pending`.
Expected behaviour, not a fault.
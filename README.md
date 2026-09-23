# Avatar Content Pipeline

Automated pipeline: topic → script → voice → avatar video → edit →
human approval → YouTube. Orchestrated with self-hosted n8n.

## Running locally

    cp .env.example .env     # then fill in real values
    docker compose up -d

n8n: http://localhost:5678

## Layout

    workflows/   exported n8n workflow JSON
    db/          SQL schema and migrations
    scripts/     ffmpeg and helper scripts
    assets/      intro/outro, music, caption font
    docs/        architecture, runbook, build log, decisions
    files/       runtime scratch (gitignored), mounted at /files

## Workflows

| File | Purpose |
|---|---|
| `pipeline.json` | Orchestrator — reads pending rows, calls each stage, writes results back |
| `generate-script.json` | Sub-workflow — topic in, structured script out |
| `async-job-pattern.json` | Reference pattern for long-running jobs (submit, poll, give up) |
| `error-alert.json` | Error workflow — logs uncaught failures to the errors tab |

Import a workflow with **⋯ → Import from File**. Credentials are not included
in exports; create them and reselect them in each node.
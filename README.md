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
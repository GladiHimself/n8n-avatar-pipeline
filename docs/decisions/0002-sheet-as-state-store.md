# 0002 — Google Sheets as the pipeline state store

Status: Accepted
Date: 2026-09-23

## Context

Each video moves through several stages over minutes to hours. The pipeline
needs somewhere to record which stage each video has reached, so that runs
are restartable and progress is visible. The client also needs a way to
submit topics without being given a tool to learn.

## Decision

A single Google Sheet, one row per video, with a `status` column acting as
the state machine. It is both the input surface and the state store.

Postgres is already running behind n8n and would be the conventional choice.
It was not chosen because the client cannot open it. The sheet gives them
a familiar interface for adding topics and a live view of progress, at the
cost of query power we do not currently need.

## Consequences

Positive: zero client training; progress is visible at a glance; rows are
editable by hand, so a human can correct or re-queue anything; no extra
infrastructure.

Negative: no transactions, no constraints, no real types — a trailing space
in a cell silently breaks a filter. Google API rate limits apply. At high
volume this would not hold.

Neutral: migrating to Postgres later means changing the read and write nodes
in pipeline only, since no other component touches the sheet. If the client
ever needs proper reporting, that is the path.
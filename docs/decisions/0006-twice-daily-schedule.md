# 0006 — Twice-daily schedule around the approval gate

Status: accepted (Day 14)

## Context
Approval is human and asynchronous. A run can't publish a video nobody has approved yet.

## Decision
Schedule Trigger `7 10,18 * * *` (Asia/Kolkata). The morning run takes new rows to
awaiting_approval; the evening run publishes whatever was approved during the day.
Limit 1 per run until the Day 15 daily cap. Minute 7 keeps scheduled runs distinguishable from manual ones.

## Consequences
- Max 2 new videos/day; an approval takes ≤ 8h to publish.
- Missed runs (Mac asleep, Docker down) are skipped, not replayed. Production needs an always-on host.
- No run lock yet: avoid manual runs near 10:07/18:07 (lock comes Day 15).
- Google OAuth app moved to Production (unverified) so refresh tokens no longer expire every 7 days.
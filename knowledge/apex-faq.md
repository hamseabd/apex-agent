# Apex FAQ

Apex is a self-hosted Telegram health accountability bot. It tracks the metrics
in your personal protocol (`apex.yaml`) and can answer questions grounded in the
documents in this knowledge base.

## How do I log something?
Just tell the bot naturally, e.g. "slept 7 hours" or "hit 180g protein". It logs
the value and shows progress toward your daily target.

## What is the knowledge base?
Any markdown/text file the operator places under `knowledge/` in the Apex S3
bucket. The bot answers research questions using ONLY these documents and cites
the source filename. If no document covers a question, it says so instead of guessing.

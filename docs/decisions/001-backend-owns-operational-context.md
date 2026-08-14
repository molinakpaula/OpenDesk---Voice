# ADR 001: FastAPI Owns Operational Context and Disclosure

- Status: Accepted
- Date: 2026-08-14

## Context

The voice model can conduct a natural conversation, but unconstrained language
models may infer missing facts or reveal information outside a caller's role.

## Decision

FastAPI is the source of truth for lot facts, caller assignments, role-specific
fields, escalation signals, and the final `spoken_message`. ElevenLabs speaks
the returned message without adding operational details.

## Alternatives considered

- Put all records and rules in the system prompt.
- Let the language model query raw records and decide what to reveal.

## Consequences

- Privacy and safety rules are deterministic and testable.
- Voice prompts stay focused on conversation orchestration.
- Backend changes require deployment, but do not depend on model behavior.

# ADR 007: Use a separate after-hours order-intake agent

## Status

Accepted for the first order-intake milestone.

## Context

The existing MaderaFlow agent retrieves sample lot status for known callers.
The new Maderera Las Garzas workflow collects personal contact and commercial
request information from new callers. It also needs consent, persistence,
post-call transcripts, notification delivery, and country-specific questions.

Combining these purposes in one prompt would make tool selection, privacy
boundaries, testing, and reviewer understanding less reliable.

## Decision

Keep the existing lot-status agent and create a separate Spanish/German/English
after-hours order-intake agent. Both may call the same FastAPI deployment, but
they use different protected endpoints, prompts, and data stores.

The order agent uses one idempotent `POST /order-requests` operation. The API
owns conditional field validation, request-number generation, escalation, and
notification state. ElevenLabs owns speech, language switching, and one-question-
at-a-time conversation flow.

## Consequences

- A failure or prompt change in order intake does not break the portfolio demo.
- Order data can receive stricter retention and access controls.
- The user must manage two agents and route telephone numbers deliberately.
- Shared components can be extracted later after both workflows are stable.

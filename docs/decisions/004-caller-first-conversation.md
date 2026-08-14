# ADR 004: Use a Caller-ID-First Conversation

- Status: Accepted
- Date: 2026-08-14

## Context

Asking callers to provide a role, caller ID, lot ID, and internal intent creates
an unnatural voice interaction. The backend already knows the caller's role and
assignments.

## Decision

Require only `caller_id` on the first webhook call. Return assigned lot IDs and
ask for a selection when several exist. Infer intent from the caller's role when
the lot is known.

## Alternatives considered

- Require all context before the first tool call.
- Let the language model guess a role or choose a lot.
- Return detailed summaries for every assigned lot in one long response.

## Consequences

- The caller answers fewer technical questions.
- The backend controls role and assignment validation.
- A second turn remains necessary when one caller has several assigned lots.

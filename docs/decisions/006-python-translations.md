# ADR 006: Keep Initial Translations in Python

- Status: Accepted
- Date: 2026-08-14

## Context

The support response must use approved English, Spanish, or Portuguese wording
without allowing the voice model to translate or invent operational details.

## Decision

Keep response templates and operational labels in Python, covered by automated
tests. The active conversation language is independent from caller role.

## Alternatives considered

- Ask the language model to translate each response.
- Add a translation service or content-management system.
- Maintain separate agents for each language.

## Consequences

- Wording is deterministic, reviewable, and protected by tests.
- Copy changes require code review and deployment.
- A translation catalog may be preferable when non-developers need to maintain
  many languages or large amounts of content.

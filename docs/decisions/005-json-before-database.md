# ADR 005: Use Validated JSON Before Adding a Database

- Status: Accepted
- Date: 2026-08-14

## Context

The current milestone demonstrates retrieval, multilingual responses, privacy,
and voice-tool integration with a small fixed dataset.

## Decision

Store sample business records in version-controlled JSON and validate all
relationships at startup. Do not add PostgreSQL or Supabase yet.

## Alternatives considered

- Introduce PostgreSQL immediately.
- Hard-code every record inside Python.

## Consequences

- Reviewers can understand and edit the dataset without infrastructure.
- Tests remain fast and deterministic.
- There are no writes, transactions, concurrency controls, or persistent
  history. A database becomes necessary before live operational use.
